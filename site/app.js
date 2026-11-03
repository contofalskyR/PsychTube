/* PsychTube — static, no accounts. State lives in this browser. */
(function () {
  "use strict";
  const PT = window.PT;
  if (!PT) { document.getElementById("main").innerHTML = "<div class='empty'><h2>No data loaded</h2><p>data.js is missing. Run <code>python3 pipeline/build_catalog.py</code>.</p></div>"; return; }

  // ------------------------------------------------------------ data indexes
  const V = PT.videos;
  // data.js omits empty fields to stay small; restore the defaults the templates rely on
  for (const v of V) {
    for (const k of ["communities", "vouches", "clips", "rel", "kw", "cw", "topics"]) if (!v[k]) v[k] = [];
    if (!v.src) v.src = {};
    for (const k of ["why", "summary", "quote", "ch"]) if (v[k] == null) v[k] = "";
    for (const k of ["nrec", "nmention", "months", "score"]) if (v[k] == null) v[k] = 0;
    if (v.badge === undefined) v.badge = null;
    if (v.shelf === undefined) v.shelf = [];
    if (v.orig === undefined) v.orig = null;
  }
  // ------------------------------------------------------------ ranking: long-form content is ordered by legitimacy first
  // For anything over 25 minutes the order of preference is: a taught course or lecture series an institution published
  // (or a curated shelf copy, or a long video on an institution's own channel), then the institutions' seminars, grand
  // rounds and conference talks (institutional, but a speaker's own account and not a course), then fireside chats,
  // interviews and independent talks — including lecturers' channels whose affiliation could not be verified — then
  // podcasts. Short pieces (a demo, a clip, a TED talk) are not penalised. The community score still orders items within
  // a tier, so a strongly vouched interview outranks a plain course lecture, but a podcast episode needs several
  // recommenders to climb past one.
  const LONG_FORM = 25 * 60;
  const PODCAST_RX = /podcast|huberman|lex fridman|rogan|modern wisdom|diary of a ceo|tim ferriss|rich roll|jordan harbinger|chris williamson|theo von|impact theory|the knowledge project|making sense|mindscape|lunar society|dwarkesh|econtalk|hidden brain|ologies|armchair expert/i;
  const INST_CH = new Set(PT.inst_channels || []);   // channels the institutions publish on
  const series = new Map(PT.series.map(s => [s.id, s]));
  const TIER = { course: 0, talk: 1, fireside: 2, podcast: 3 };
  function formTier(v) {
    if (!v.len || v.len < LONG_FORM) return TIER.course;
    if (v.type === "podcast" || PODCAST_RX.test(v.ch || "")) return TIER.podcast;   // checked first: a podcast in a department's playlist is still a podcast
    if (v.inst && v.inst.ok === false) return TIER.fireside;                        // a lecturer's channel with no verified affiliation: not the institution's word
    if (v.orig) return TIER.course;
    if (v.inst) {
      const sd = v.series ? series.get(v.series) : null;
      return (sd && sd.kind === "talks") || (v.inst.loose && v.type !== "lecture") ? TIER.talk : TIER.course;
    }
    if (v.chid && INST_CH.has(v.chid)) return TIER.course;                           // the institution's own channel, outside any pulled playlist
    return TIER.fireside;
  }
  const TIER_WEIGHT = [1, 0.75, 0.5, 0.25];
  const byId = new Map(V.map(v => [v.id, v]));
  for (const sd of PT.series) for (const id of sd.vids) { const v = byId.get(id); if (v && !v.series) v.series = sd.id; }   // the series link is needed before ranking
  for (const v of V) { v.tier = formTier(v); v.rank = Math.max(v.score, 1) * TIER_WEIGHT[v.tier]; }
  // browsing order: tier first, then the weighted score. A strongly vouched podcast still ranks above other podcasts and
  // keeps its place in search and on the canon, but on a topic page the institutions' own long-form comes before it.
  const byLegitimacy = (a, b) => (a.tier - b.tier) || (b.rank - a.rank) || (b.score - a.score);
  V.sort(byLegitimacy);
  const topics = new Map();
  const areaOf = new Map();
  const areas = PT.areas;
  for (const a of areas) for (const t of a.topics) { topics.set(t.id, t); areaOf.set(t.id, a); }
  const maxScore = Math.max(...V.map(v => v.score));
  const SRC_NAME = { hn: "Hacker News", reddit: "Reddit", se: "Psych SE" };
  const INST_SERIES = PT.series.filter(sd => sd.inst);
  const KINDS = { course: INST_SERIES.filter(sd => sd.kind === "course").length, series: INST_SERIES.filter(sd => sd.kind === "series").length, talks: INST_SERIES.filter(sd => sd.kind === "talks").length };
  const PUBLISHERS = (PT.institutions || []).filter(i => i.courses && !/^Independent lecturer/.test(i.name)).length;   // lecturers' own channels are not institutions
  const LECTURERS = new Set(INST_SERIES.filter(sd => /^Independent lecturer/.test(sd.inst)).map(sd => sd.chid || sd.ch)).size;   // distinct channels, not institution labels

  // ------------------------------------------------------------ local state
  const store = {
    get(k, d) { try { const v = localStorage.getItem("pt:" + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem("pt:" + k, JSON.stringify(v)); } catch (e) { /* private mode etc. */ } },
  };
  const state = {
    history: store.get("history", []),      // [{id, ts}] newest first
    liked: new Set(store.get("liked", [])),
    later: new Set(store.get("later", [])),
    settings: Object.assign({ theme: window.PT_ARTIFACT ? "system" : "dark", thumbs: "mid", hideCare: false, hideCW: true, autoplay: true, autoNext: "ask", keys: true }, store.get("settings", {})),
    progress: store.get("progress", {}),    // id -> {t: seconds watched up to, d: duration, done, ts}
  };
  const ART = !!window.PT_ARTIFACT;                 // hosted copy: no embeds, no external images
  const FROM_DISK = location.protocol === "file:";  // YouTube's player refuses to embed without a web referrer (Error 153)
  const LINKOUT = ART || FROM_DISK;                 // show a poster + "Watch on YouTube" instead of the player
  const THUMBS = window.PT_THUMBS || {};            // id -> data URI (hosted copy only)
  const saveSettings = () => store.set("settings", state.settings);
  const effectiveTheme = () => { const a = document.documentElement.getAttribute("data-theme"); if (a) return a; return matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark"; };
  const applyTheme = () => {
    const t = state.settings.theme;
    if (t === "system") { if (!ART) document.documentElement.removeAttribute("data-theme"); }
    else document.documentElement.setAttribute("data-theme", t);
    document.getElementById("themeBtn").textContent = effectiveTheme() === "dark" ? "☾" : "☀";
  };
  applyTheme();
  try { matchMedia("(prefers-color-scheme: light)").addEventListener("change", applyTheme); } catch (e) { /* old browsers */ }

  // ------------------------------------------------------------ helpers
  const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmtDur = s => { if (!s) return ""; const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = s % 60; return h ? `${h}:${String(m).padStart(2, "0")}:${String(x).padStart(2, "0")}` : `${m}:${String(x).padStart(2, "0")}`; };
  const fmtLen = s => { if (!s) return ""; const h = Math.floor(s / 3600), m = Math.round((s % 3600) / 60); return h ? `${h} h ${m ? m + " min" : ""}`.trim() : `${m} min`; };
  const fmtViews = n => !n ? "" : n >= 1e6 ? (n / 1e6).toFixed(n >= 1e7 ? 0 : 1) + "M views" : n >= 1e3 ? Math.round(n / 1e3) + "K views" : n + " views";
  const plural = (n, w) => `${n} ${w}${n === 1 ? "" : "s"}`;
  const SITE_URL = "https://contofalskyr.github.io/PsychTube/";   // the live copy, where players embed in the page
  // videos are YouTube unless v.p names another provider (Panopto for courses universities host themselves)
  const PROVIDER_NAME = { youtube: "YouTube", panopto: "Panopto", archive: "the Internet Archive" };
  const providerOf = v => PROVIDER_NAME[(v && v.p) || "youtube"] || v.p;
  const vidOf = x => (typeof x === "string" ? byId.get(x) : x);
  const thumbUrl = (x, mode) => {
    const v = vidOf(x); const id = v ? v.id : x;
    if (ART) return THUMBS[id] || "";
    if (v && v.p === "panopto") return `https://${v.host}/Panopto/Services/FrameGrabber.svc/FrameRedirect?objectId=${id}&mode=Delivery&random=1`;
    if (v && v.p === "archive") return `https://archive.org/services/img/${id}`;
    return `https://i.ytimg.com/vi/${id}/${(mode || state.settings.thumbs) === "mid" ? "hq2" : "hqdefault"}.jpg`;
  };
  const watchUrl = (x, t) => {
    const v = vidOf(x); const id = v ? v.id : x;
    if (v && v.p === "panopto") return `https://${v.host}/Panopto/Pages/Viewer.aspx?id=${id}${t ? "&start=" + t : ""}`;
    if (v && v.p === "archive") return `https://archive.org/details/${id}${t ? "?start=" + t : ""}`;
    return `https://www.youtube.com/watch?v=${id}${t ? "&t=" + t + "s" : ""}`;
  };
  const embedUrl = (v, start, autoplay) => v.p === "panopto"
    ? `https://${v.host}/Panopto/Pages/Embed.aspx?id=${v.id}&autoplay=${autoplay ? "true" : "false"}&offerviewer=true&showtitle=false&showbrand=false&captions=false&interactivity=all${start ? "&start=" + start : ""}`
    : v.p === "archive"
      ? `https://archive.org/embed/${v.id}?${autoplay ? "autoplay=1&" : ""}${start ? "start=" + start : ""}`
      : `https://www.youtube-nocookie.com/embed/${v.id}?rel=0&modestbranding=1${start ? "&start=" + start : ""}${autoplay ? "&autoplay=1" : ""}`;
  const dayseed = () => { const d = new Date(); return d.getFullYear() * 400 + d.getMonth() * 31 + d.getDate(); };
  const rng = seed => () => { seed = (seed * 1664525 + 1013904223) % 4294967296; return seed / 4294967296; };
  const isWatched = id => state.history.some(h => h.id === id);
  // ---- lecture tracker: where you are in every video, and through every course (this browser only)
  let progTimer = null, progDirty = false;
  const flushProgress = () => {
    clearTimeout(progTimer); if (!progDirty) return;
    const disk = store.get("progress", {});              // another tab may have saved since we loaded: newest record per lecture wins
    for (const [k, p] of Object.entries(disk)) { const cur = state.progress[k]; if (p && (!cur || (p.ts || 0) > (cur.ts || 0))) state.progress[k] = p; }
    store.set("progress", state.progress); progDirty = false;
  };
  const saveProgress = () => { progDirty = true; clearTimeout(progTimer); progTimer = setTimeout(flushProgress, 800); };
  const progOf = id => state.progress[id] || null;
  const isDone = id => !!(state.progress[id] && state.progress[id].done);
  const pctOf = v => { const p = state.progress[v.id]; if (!p) return 0; if (p.done) return 100; const d = p.d || v.len; return d ? Math.max(1, Math.min(99, Math.round(100 * p.t / d))) : 0; };
  const resumeAt = v => { const p = state.progress[v.id]; if (!p || p.done) return 0; const d = p.d || v.len || 0; return p.t > 45 && (!d || d - p.t > 60) ? Math.max(0, Math.floor(p.t) - 5) : 0; };
  function setProgress(id, t, d) {
    const cur = state.progress[id] || {}; const v = byId.get(id); d = d || cur.d || (v && v.len) || 0; t = Math.max(0, t || 0);
    const done = cur.done || (d > 0 && (t >= d - 45 || t / d >= 0.92));
    state.progress[id] = { t: Math.floor(Math.max(t, done ? t : 0)), d: Math.floor(d), done, ts: Date.now() };
    saveProgress();
  }
  function markDone(id, done) {
    const cur = state.progress[id] || {}; const v = byId.get(id);
    if (done) state.progress[id] = { t: cur.d || (v && v.len) || cur.t || 0, d: cur.d || (v && v.len) || 0, done: true, ts: Date.now() };
    else state.progress[id] = { t: 0, d: cur.d || (v && v.len) || 0, done: false, ts: Date.now() };   // a dated record, so a merge can't resurrect the old one
    progDirty = true; flushProgress();
  }
  const seriesProgress = sd => { const n = sd.vids.length; const done = sd.vids.filter(isDone).length; const partial = sd.vids.reduce((a, id) => a + (isDone(id) ? 0 : (pctOf(byId.get(id) || { id }) / 100)), 0); const pct = n ? Math.round(100 * (done + partial) / n) : 0; const last = Math.max(0, ...sd.vids.map(id => (state.progress[id] || {}).ts || 0)); const leftSec = sd.vids.reduce((a, id) => { const v = byId.get(id); if (!v || !v.len) return a; const p = state.progress[id]; return a + (p && p.done ? 0 : Math.max(0, v.len - ((p && p.t) || 0))); }, 0); return { n, done, pct, last, leftSec, started: last > 0 }; };
  const nextInSeriesFor = sd => { const open = sd.vids.find(id => !isDone(id)); return open || sd.vids[0]; };
  const progressBar = v => { const p = pctOf(v); return p > 0 && p < 100 ? `<i class="prog" style="width:${p}%" aria-label="${p}% watched"></i>` : ""; };
  const doneBadge = v => isDone(v.id) ? `<span class="done-badge" title="Watched">✓</span>` : "";
  const visible = v => (!state.settings.hideCare || !careWorthy(v)) && (!state.settings.hideCW || !v.cw.length);

  // ------------------------------------------------------------ card templates
  function communityChips(v, max) {
    const seen = new Set(); const out = [];
    for (const c of v.communities) {
      const src = c === "Hacker News" ? "hn" : c.startsWith("r/") ? "reddit" : "se";
      const label = c === "Psychology & Neuroscience SE" ? "Psych SE" : c;
      if (seen.has(label)) continue; seen.add(label);
      out.push(`<span class="chip ${src}">${esc(label)}</span>`);
      if (out.length >= (max || 3)) break;
    }
    const more = v.communities.length - out.length;
    return out.join("") + (more > 0 ? `<span class="faint">+${more}</span>` : "");
  }
  const LECTURER_GROUP = "Independent lecturer";                       // the build's name for lecturers' own channels
  const instShort = name => { const i = (PT.institutions || []).find(x => x.name === name); return i ? i.short : name; };
  // the chip names the publisher: the institution's short name, or — on a lecturer's own channel — the lecturer
  const instLabel = inst => inst.n === LECTURER_GROUP ? (inst.u || "a lecturer's channel") : instShort(inst.n);
  const instTitle = inst => inst.n === LECTURER_GROUP ? `Published on ${inst.u ? inst.u + "'s" : "a lecturer's"} own channel${inst.ok === false ? " (affiliation not verified)" : ""}` : `Published by ${inst.n}${inst.u ? " · " + inst.u : ""}${inst.ok === false ? " (publisher not verified)" : ""}`;
  const instChip = v => v.inst ? `<span class="chip inst ${v.inst.ok === false ? "unverified" : ""}" title="${esc(instTitle(v.inst))}">${esc(instLabel(v.inst))}</span>` : "";
  const kindWord = v => { const sd = series.get(v.series); return sd && sd.kind === "talks" ? "talk" : "lecture"; };
  function vouchLine(v, max) {
    const n = v.nrec || 0;
    if (!n && v.inst) return `<div class="vouch"><span class="pub">${v.inst.n === LECTURER_GROUP ? "Lecturer's channel" : "Published by"}</span> ${instChip(v)}<span class="faint">${v.inst.loose ? (v.type === "lecture" ? "standalone lecture" : "standalone talk") : `${kindWord(v) === "talk" ? "seminar talk" : "lecture"} ${v.inst.i} of ${v.inst.of}`}${v.inst.ok === false ? " · not verified" : ""}</span></div>`;
    if (!n && v.orig) return `<div class="vouch"><span class="pub">${v.orig.form && !/^(original|demonstration|session|clinical|teaching|role|training)/.test(v.orig.form) ? esc(v.orig.form[0].toUpperCase() + v.orig.form.slice(1)) : (SHELF_LABEL[v.orig.shelf] || "Primary source")}</span><span class="faint">${esc((v.orig.uploader || "").split(" (")[0].slice(0, 40))}${v.orig.year ? ` · ${v.orig.year}` : ""}</span></div>`;
    if (!n) return v.nmention ? `<div class="vouch"><span class="faint">cited ${plural(v.nmention, "time")}, not recommended</span> ${communityChips(v, max)}</div>` : "";
    return `<div class="vouch"><span class="n">${n}</span>${n === 1 ? "vouch" : "vouches"} ${communityChips(v, max)}${instChip(v)}</div>`;
  }
  const SHELF_LABEL = { originals: "Primary source", demos: "Demo", therapy: "Therapy demo", cases: "Clinical case" };
const SHELF_HEAD = { originals: "Primary source", demos: "Try it yourself", therapy: "Therapy in practice", cases: "Clinical case on film" };
const SHELF_SUB = { originals: "The original films of the classic experiments, from the archives that hold them, each with its paper.", demos: "Experiments that work on you, from the researchers' own channels, each with its paper.", therapy: "Full sessions, role-plays and simulated interviews from training institutes and university programs: therapy as it is done, not lectures about it.", cases: "Neuropsychology's textbook patients as they present: aphasia, neglect, face blindness, blindsight, phantom limbs — from the hospitals', labs' and archives' own copies, each with its paper." };
const STATUS_LABELS = PT.status_labels || { replicated: "Replicated", smaller: "Smaller than claimed", mixed: "Mixed evidence", failed: "Did not replicate", overstated: "Overstated", misreported: "Misreported", myth: "Myth", fraud: "Fraud or retraction", reversed: "Reversed" };
  const GOOD_STATUS = new Set(["replicated"]);
  const statusOf = id => (PT.contested[id] || {}).status || "mixed";
  const statusLabel = id => STATUS_LABELS[statusOf(id)] || "Contested";
  const statusChip = (id, extra) => `<span class="status s-${esc(statusOf(id))}${extra ? " " + extra : ""}">${esc(statusLabel(id))}</span>`;
  const careWorthy = v => !!(v.badge && v.badge.role !== "critique" && !GOOD_STATUS.has(statusOf(v.badge.id)));   // a replicated finding is not a warning
  function tagFor(v, idx) {
    const c = v.badge ? PT.contested[v.badge.id] : null;             // a badge for a finding the taxonomy no longer has is ignored, not a crash
    if (c && v.badge.role === "critique") return `<span class="tag critique">Pushback</span>`;
    if (c && GOOD_STATUS.has(statusOf(v.badge.id))) return `<span class="tag good" title="${esc(c.name)}">Replicated</span>`;
    if (c) return `<span class="tag s-${esc(statusOf(v.badge.id))}" title="${esc(c.name)}">${esc(statusLabel(v.badge.id))}</span>`;
    if (idx != null) return `<span class="tag series">${idx}</span>`;
    return "";
  }
  const hueOf = s => { let h = 0; for (const c of String(s)) h = (h * 31 + c.charCodeAt(0)) % 360; return h; };
  function placeholder(v) {
    // hosted copy has no thumbnails for course lectures: a numbered tile in the course's colour stands in
    if (v.inst) return `<div class="ph lec" style="--h:${hueOf(v.series)}" aria-hidden="true"><b>${v.inst.i}</b><span>${esc(instShort(v.inst.n))}</span></div>`;
    return `<div class="ph" aria-hidden="true">${esc((v.title || "?").trim()[0] || "?")}</div>`;
  }
  const img = id => { const u = thumbUrl(id); return u ? `<img loading="lazy" src="${u}" alt="" data-fb="1" onerror="window.__ptImgErr(this)">` : ""; };
  const thumbInner = (v, idx) => `${placeholder(v)}${img(v.id)}${tagFor(v, idx)}${doneBadge(v)}${v.len ? `<span class="pill">${fmtDur(v.len)}</span>` : ""}${progressBar(v)}`;
  function thumb(v, idx) {
    return `<div class="thumb ${isDone(v.id) ? "is-done" : ""}">${thumbInner(v, idx)}</div>`;
  }
  window.__ptPoster = (img, id, failed) => {
    // hq720 -> hq2 (frame from the middle) -> hqdefault; a 120px-wide "image" is YouTube's placeholder, not a frame
    const steps = ["hq720", "hq2", "hqdefault"]; const i = +img.dataset.step;
    if (!failed && img.naturalWidth > 200) return;
    if (i >= steps.length - 1) { if (failed) img.style.visibility = "hidden"; return; }
    img.dataset.step = String(i + 1); img.src = `https://i.ytimg.com/vi/${id}/${steps[i + 1]}.jpg`;
  };
  window.__ptImgErr = img => {
    if (ART || !img.src || /FrameGrabber|archive\.org/.test(img.src)) { img.style.visibility = "hidden"; return; }
    if (img.dataset.fb === "1") { img.dataset.fb = "2"; img.src = img.src.replace(/\/(hq2|hqdefault)\.jpg/, "/hqdefault.jpg"); }
    else if (img.dataset.fb === "2") { img.dataset.fb = "3"; img.src = img.src.replace("hqdefault", "mqdefault"); }
    else { img.style.visibility = "hidden"; }
  };
  const card = (v, opts = {}) => `<a class="card ${opts.cls || ""}" href="#v-${v.id}" data-id="${v.id}">${thumb(v, opts.idx)}<div class="body"><div class="title">${esc(v.title)}</div><div class="ch">${esc(v.ch || "")}</div>${opts.noVouch ? "" : vouchLine(v, opts.chips)}${opts.desc ? `<div class="desc">${esc(v.why || v.summary)}</div>` : ""}</div></a>`;
  const grid = (list, opts) => list.length ? `<div class="grid">${list.map(v => card(v, opts)).join("")}</div>` : "";
  const rowOf = (list, opts) => `<div class="row">${list.map(v => card(v, opts)).join("")}</div>`;
  // Long lists (an area page is ~7,000 cards, 15 s of main-thread work on a mid-range phone) render a page at a time.
  // The next page comes from a button, never from scrolling: rows still end.
  const PAGE = 60;
  const moreBtn = left => `<p style="margin:18px 0"><button class="btn quiet" data-more>Show ${Math.min(PAGE, left)} more <span class="faint">· ${left.toLocaleString()} left</span></button></p>`;
  const paged = (list, opts, open) => `${open || `<div class="grid" data-paged>`}${list.slice(0, PAGE).map(v => card(v, opts)).join("")}</div>${list.length > PAGE ? moreBtn(list.length - PAGE) : ""}`;
  function wireMore(list, opts) {
    const box = main.querySelector("[data-paged]"); let btn = main.querySelector("[data-more]"); if (!box || !btn) return;
    let shown = PAGE;
    const more = () => {
      const first = list[shown];
      box.insertAdjacentHTML("beforeend", list.slice(shown, shown + PAGE).map(v => card(v, opts)).join(""));
      shown += PAGE;
      const next = box.querySelector(`[data-id="${first.id}"]`); if (next) next.focus({ preventScroll: true });   // keyboard users land on the first new card
      const left = list.length - shown;
      if (left <= 0) btn.parentNode.remove(); else { btn.parentNode.outerHTML = moreBtn(left); btn = main.querySelector("[data-more]"); btn.onclick = more; }
    };
    btn.onclick = more;
  }
  const SEG_LABEL = { sort: "Sort", src: "Source", dur: "Length", shelf: "Shelf", level: "Level" };
  const SMOOTH = () => (matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth");
  const section = (title, body, more, sub) => body ? `<section class="section"><div class="section-head"><div><h2>${title}</h2>${sub ? `<div class="sub">${sub}</div>` : ""}</div>${more ? `<a class="more" href="${more}">See all</a>` : ""}</div>${body}</section>` : "";

  // Two-step confirmation inside the page: the button turns into "Really? Yes / No". (The hosted copy runs in a frame where
  // confirm() returns false without showing anything, so a dialog would make the button a no-op there.)
  function armConfirm(btn, question, onYes) {
    if (!btn) return;
    btn.onclick = () => {
      const wrap = document.createElement("span"); wrap.className = "confirm"; wrap.setAttribute("role", "group"); wrap.setAttribute("aria-label", question);
      wrap.innerHTML = `<span class="muted">${esc(question)}</span> <button class="btn danger" type="button">Yes, clear</button> <button class="btn quiet" type="button">No</button>`;
      const [yes, no] = wrap.querySelectorAll("button");
      yes.onclick = () => { onYes(); };
      no.onclick = () => { wrap.replaceWith(btn); btn.focus(); };
      btn.replaceWith(wrap); yes.focus();
    };
  }
  // ------------------------------------------------------------ recommendation
  function forYou(n) {
    const hist = state.history.slice(0, 40);
    const out = new Map();
    const watched = new Set(state.history.map(h => h.id));
    if (!hist.length) {
      // a fresh mix: the best video of each topic, rotated by day
      const r = rng(dayseed());
      const picks = [];
      const used = new Set();
      const tops = [...topics.keys()];
      for (let i = tops.length - 1; i > 0; i--) { const j = Math.floor(r() * (i + 1)); [tops[i], tops[j]] = [tops[j], tops[i]]; }   // Fisher–Yates: the same row in every browser on the same day
      for (const t of tops) {
        const cands = V.filter(v => visible(v) && v.topics[0] === t && !used.has(v.id) && !careWorthy(v) && (v.nrec >= 2 || v.score >= 2.5)).slice(0, 3);
        if (!cands.length) continue;
        const pick = cands[Math.floor(r() * cands.length)];
        used.add(pick.id); picks.push(pick);
        if (picks.length >= n) break;
      }
      return picks;
    }
    const topicW = new Map(), chanW = new Map(), seriesW = new Map();
    hist.forEach((h, i) => {
      const v = byId.get(h.id); if (!v) return;
      const w = 1 / (1 + i * 0.12);
      v.topics.forEach((t, k) => topicW.set(t, (topicW.get(t) || 0) + w * (1 - k * 0.3)));
      if (v.ch) chanW.set(v.ch, (chanW.get(v.ch) || 0) + w);
      if (v.series) seriesW.set(v.series, (seriesW.get(v.series) || 0) + w);
      for (const r of v.rel || []) out.set(r, (out.get(r) || 0) + 3 * w);
    });
    for (const v of V) {
      if (watched.has(v.id) || !visible(v)) continue;
      let s = out.get(v.id) || 0;
      v.topics.forEach((t, k) => { s += (topicW.get(t) || 0) * (1 - k * 0.3); });
      s += (chanW.get(v.ch) || 0) * 0.6;
      s += (seriesW.get(v.series) || 0) * 2;
      s += 0.6 * v.score / maxScore;
      if (s > 0.6 * v.score / maxScore) out.set(v.id, s);
      else out.delete(v.id);
    }
    const ranked = [...out.entries()].filter(([id]) => !watched.has(id) && byId.has(id)).sort((a, b) => b[1] - a[1]);
    // light diversity: at most 3 per channel
    const perCh = new Map(); const picks = [];
    for (const [id] of ranked) {
      const v = byId.get(id); const c = perCh.get(v.ch) || 0;
      if (c >= 3) continue; perCh.set(v.ch, c + 1); picks.push(v);
      if (picks.length >= n) break;
    }
    return picks;
  }

  // ------------------------------------------------------------ search
  const norm = s => (s || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  const words = s => " " + norm(s).replace(/[^a-z0-9\u00c0-\u024f]+/g, " ").trim() + " ";      // " word word " so a match can be anchored at a word start
  const STOPWORDS = new Set("a an and are as at be by can do does for how in is it its of on or the to what why with".split(" "));
  // "prosopagnosia" -> "prosopagnos" finds "prosopagnosic"; "neurons" -> "neuron"; "placebo" stays "placebo"
  const stem = t => { const s = t.replace(/(ics|ic|ias|ia|ies|es|s|ing|ed|al)$/, ""); return t.length >= 6 && s.length >= 5 ? s : t; };
  let index = null;   // built on the first search, not at start-up
  const buildIndex = () => V.map(v => {
    const sd = v.series ? series.get(v.series) : null;
    return {
      v,
      title: words(v.title), ch: words([v.ch, v.inst ? v.inst.n : "", sd && sd.inst ? sd.name + " " + (sd.lecturer || "") + " " + (sd.short || "") : ""].join(" ")),
      topicText: words(v.topics.map(t => topics.get(t) ? topics.get(t).name + " " + topics.get(t).desc : t).join(" ")),
      text: words([v.why, v.summary, v.quote, (v.kw || []).join(" "), v.communities.join(" "), ...v.vouches.map(x => x.q)].join(" ")),
    };
  });
  function search(q, limit) {
    if (!index) index = buildIndex();
    // long terms match on their stem so "prosopagnosia" finds "prosopagnosics", "amnesia" finds "amnesic", "aphasia" "aphasic"
    const all = norm(q).split(/[^a-z0-9\u00c0-\u024f]+/).filter(Boolean);
    const terms = (all.some(t => !STOPWORDS.has(t)) ? all.filter(t => !STOPWORDS.has(t)) : all).map(t => (t.length <= 2 ? " " + t + " " : " " + stem(t)));   // short terms must be whole words
    if (!terms.length) return [];
    const res = [];
    for (const e of index) {
      let s = 0, ok = true;
      for (const t of terms) {
        let ts = 0;
        if (e.title.includes(t)) ts += 6 + (e.title.startsWith(t) ? 2 : 0);   // startsWith(" term"): the title begins with it
        if (e.ch.includes(t)) ts += 4;
        if (e.topicText.includes(t)) ts += 2;
        if (e.text.includes(t)) ts += 1;
        if (!ts) { ok = false; break; }
        s += ts;
      }
      if (ok) res.push([s + Math.log1p(e.v.rank), e.v]);
    }
    return res.sort((a, b) => b[0] - a[0]).slice(0, limit || 200).map(x => x[1]);
  }

  // ------------------------------------------------------------ pages
  const main = document.getElementById("main");
  function setNav(id) { document.querySelectorAll(".rail a").forEach(a => { if (a.dataset.nav === id) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current"); }); }
  function setTitle(t) { if (t) { const ta = document.createElement("textarea"); ta.innerHTML = t; t = ta.value; } document.title = t ? `${t} — PsychTube` : "PsychTube"; }

  // ---- "Teach me something I don't know": a background picker (no account) that serves the fields next door
  const BACKGROUNDS = [
    ["cogsci", "Cognitive science research", ["memory", "attention-focus", "learning-studying", "intelligence-expertise", "creativity-insight", "language-thought", "rationality-biases", "decision-risk", "ai-and-mind"]],
    ["neuro", "Neuroscience", ["how-the-brain-works", "perception-illusions", "sleep-dreams", "neurochemistry", "brain-disorders", "brain-tech", "animal-minds"]],
    ["clinical", "Clinical / counselling", ["depression-anxiety", "adhd-autism", "trauma-stress", "addiction", "therapy", "psychiatry-medication", "psychedelics", "mindfulness-meditation", "serious-mental-illness", "grief-loneliness"]],
    ["psychiatry", "Medicine / psychiatry", ["psychiatry-medication", "serious-mental-illness", "brain-disorders", "neurochemistry", "addiction", "depression-anxiety", "psychedelics"]],
    ["social", "Social psychology", ["conformity-obedience", "persuasion-manipulation", "morality-cooperation", "groups-prejudice", "relationships-attachment", "tech-and-mind"]],
    ["dev", "Developmental / education", ["child-development", "parenting", "adolescence-aging", "sex-gender", "behavioral-genetics", "education-teaching"]],
    ["personality", "Personality & emotion", ["personality", "emotion", "motivation-habits", "happiness-meaning", "behavioral-genetics"]],
    ["philosophy", "Philosophy of mind", ["consciousness", "free-will", "ai-and-mind", "history-of-psychology"]],
    ["ml", "AI / machine learning", ["ai-and-mind", "brain-tech", "intelligence-expertise", "decision-risk"]],
    ["methods", "Stats / methods / meta-science", ["psych-research", "replication-crisis", "pseudoscience-skepticism"]],
    ["applied", "Applied / organisational", ["work-organizations", "design-behavior", "performance", "crime-forensic", "persuasion-manipulation"]],
    ["curious", "Just curious, no background", []],
  ];
  const BG = Object.fromEntries(BACKGROUNDS.map(([id, name, t]) => [id, { id, name, topics: new Set(t) }]));
  let teachShuffle = 0;
  function teachPicks() {
    const mine = (state.settings.background || []).map(b => BG[b]).filter(Boolean);
    const home = new Set(); for (const b of mine) for (const t of b.topics) home.add(t);
    const seen = new Set(state.history.map(h => h.id));
    const seed = Math.floor(Date.now() / 864e5) * 131 + teachShuffle * 7919 + mine.length;
    const r = rng(seed);
    const pick = (list) => list.length ? list[Math.floor(r() * list.length)] : null;
    const away = v => visible(v) && !seen.has(v.id) && !home.has(v.topics[0]) && !v.topics.some(t => home.has(t));
    const usedAreas = new Set(), usedTopics = new Set();
    const take = (list, n) => { const out = []; let guard = 0; while (out.length < n && list.length && guard++ < 60) { const v = pick(list); if (!v) break; if (usedTopics.has(v.topics[0]) || (usedAreas.has(v.area) && usedAreas.size < 4)) { list = list.filter(x => x !== v); continue; } out.push(v); usedAreas.add(v.area); usedTopics.add(v.topics[0]); list = list.filter(x => x !== v); } return out; };
    // three kinds of pick: a talk people vouched for, the first lecture of a taught course, a primary source or demo
    const talks = V.filter(v => away(v) && v.nrec >= 2 && !careWorthy(v)).slice(0, 400);
    const firstLectures = V.filter(v => away(v) && v.inst && v.inst.i === 1 && series.get(v.series) && series.get(v.series).kind === "course" && series.get(v.series).level !== "advanced");
    const originals = V.filter(v => away(v) && v.orig);
    const picks = [...take(talks, 1).map(v => [v, "a talk people vouched for"]), ...take(firstLectures, 1).map(v => [v, "lecture 1 of a course"]), ...take(originals, 1).map(v => [v, ({ demos: "an experiment to try", therapy: "therapy as it is done", cases: "a clinical case on film" })[v.orig.shelf] || "a primary source"])];
    while (picks.length < 3) { const extra = take(talks.length ? talks : V.filter(away), 1); if (!extra.length) break; picks.push([extra[0], "another field"]); }
    return { picks, mine };
  }
  function teachSection() {
    const chosen = state.settings.background || [];
    const { picks, mine } = teachPicks();
    const chips = BACKGROUNDS.map(([id, name]) => `<button class="bgchip" data-bg="${id}" aria-pressed="${chosen.includes(id)}">${esc(name)}</button>`).join("");
    const you = mine.length ? mine.map(b => b.name.toLowerCase()).join(" + ") : "";
    const cardsHtml = picks.map(([v, why]) => `<div class="teach-pick"><div class="teach-why">${esc(why)} · <a href="#t-${v.topics[0]}">${esc(topics.get(v.topics[0]).name)}</a></div>${card(v, { chips: 1 })}</div>`).join("");
    return `<section class="section teach" id="teach"><div class="section-head"><div><h2>Teach me something I don't know</h2><div class="sub">${chosen.length ? `Picked from outside <b>${esc(you)}</b>: ${picks.length} things from the fields next door. Nothing leaves your browser.` : "Say where you're coming from and PsychTube will pick from the fields next door — a vouched talk, the first lecture of a course, an original experiment. No account; it's remembered in this browser."}</div></div><div class="teach-actions">${chosen.length ? `<button class="btn quiet" id="teachShuffle">Shuffle</button><button class="btn quiet" id="teachChange">${picks.length ? "Change" : "Choose"}</button>` : ""}</div></div>
      <div class="bgpicker" id="bgpicker" ${chosen.length ? "hidden" : ""}><div class="bgchips">${chips}</div><div class="faint" style="margin-top:8px">Pick everything that describes you; the picks avoid those fields.</div></div>
      ${chosen.length ? `<div class="teach-grid">${cardsHtml || `<p class="faint">You have watched your way through the fields next door. Shuffle, or change your background.</p>`}</div>` : ""}</section>`;
  }
  function wireTeach() {
    const sec = document.getElementById("teach"); if (!sec) return;
    sec.querySelectorAll(".bgchip").forEach(b => b.onclick = () => {
      const id = b.dataset.bg; let cur = new Set(state.settings.background || []);
      if (id === "curious") cur = cur.has("curious") ? new Set() : new Set(["curious"]); else { cur.delete("curious"); if (cur.has(id)) cur.delete(id); else cur.add(id); }
      state.settings.background = [...cur]; saveSettings(); teachShuffle = 0; pageHome(); const el = document.getElementById("teach"); if (el) el.scrollIntoView({ block: "start", behavior: SMOOTH() });
    });
    const sh = document.getElementById("teachShuffle"); if (sh) sh.onclick = () => { teachShuffle++; pageHome(); const el = document.getElementById("teach"); if (el) el.scrollIntoView({ block: "start" }); };
    const ch = document.getElementById("teachChange"); if (ch) ch.onclick = () => { const pk = document.getElementById("bgpicker"); pk.hidden = !pk.hidden; };
  }
  function pageHome() {
    setNav("home"); setTitle("");
    const s = PT.stats;
    const fy = forYou(12);
    const canon = V.filter(v => visible(v) && v.nrec > 0).sort((a, b) => (b.cscore != null ? b.cscore : b.score) - (a.cscore != null ? a.cscore : a.score)).slice(0, 12);
    const recent = V.filter(v => visible(v) && v.last >= 2024).sort((a, b) => (b.last - a.last) || (b.score - a.score)).slice(0, 12);
    const care = V.filter(v => careWorthy(v) && !(state.settings.hideCW && v.cw.length)).slice(0, 12);
    const longs = V.filter(v => visible(v) && v.len >= 3600).slice(0, 12);
    const areaRows = areas.map(a => {
      const ids = new Set(a.topics.map(t => t.id));
      const list = V.filter(v => visible(v) && ids.has(v.topics[0])).slice(0, 12);
      return section(esc(a.name), list.length ? rowOf(list) : "", `#a-${a.id}`, `${plural(V.filter(v => ids.has(v.topics[0])).length, "video")}`);
    }).join("");
    const hidden = V.length - V.filter(visible).length;
    const comms = [...new Set(V.flatMap(v => v.communities))];
    const nSubs = comms.filter(c => c.startsWith("r/")).length;
    const where = ["Hacker News", nSubs ? `${nSubs} psychology subreddits` : null, "Psychology Stack Exchange"].filter(Boolean);
    const whereText = where.length > 1 ? where.slice(0, -1).join(", ") + " and " + where[where.length - 1] : where[0];
    const inst = s.inst || { courses: 0, lectures: 0, institutions: 0 };
    const courseRow = PT.series.filter(sd => sd.inst && sd.kind !== "talks" && sd.ok !== false).sort((a, b) => ((a.inst === LECTURER_GROUP) - (b.inst === LECTURER_GROUP)) || (b.pop - a.pop) || (b.n - a.n)).slice(0, 10);   // named institutions before lecturers' own channels; unverified publishers stay on the hub only
    const shelfRows = (PT.shelves || []).map(sh => { const vids = sh.items.map(it => it.vid && byId.get(it.vid)).filter(v => v && visible(v)).slice(0, 12); return vids.length ? section(sh.name, rowOf(vids), `#shelf-${sh.id}`, SHELF_SUB[sh.id] || sh.tagline) : ""; }).join("");   // taught courses first; seminars live on their own shelf
    const inProgress = Object.entries(state.progress).filter(([pid, p]) => !p.done && p.t > 45 && byId.has(pid)).sort((a, b) => b[1].ts - a[1].ts).map(([pid]) => byId.get(pid)).slice(0, 12);
    const myCourses = PT.series.map(sd => [sd, seriesProgress(sd)]).filter(([sd, sp]) => sp.started).sort((a, b) => b[1].last - a[1].last).slice(0, 8);
    main.innerHTML = `
      <div class="masthead">
        <h1>The psychology videos that psychology people keep telling each other to watch${inst.courses ? " — and the courses universities put online" : ""}.</h1>
        <p class="lede"><b>${(s.vouched || s.videos).toLocaleString()}</b> videos that people recommended on ${whereText} (${s.mentions.toLocaleString()} mentions in all)${inst.courses ? `, plus <b>${inst.lectures.toLocaleString()}</b> lectures and talks published by ${PUBLISHERS} universities, institutes, societies and hospitals${LECTURERS ? ` and ${LECTURERS} lecturers' own channels` : ""}: <b>${KINDS.course}</b> taught courses, <b>${KINDS.series}</b> lecture series and <b>${KINDS.talks}</b> seminar and conference collections` : ""}. No accounts, no analytics, no autoplay rabbit hole. Every card shows who vouched, or who published.${hidden ? ` <span class="faint">${hidden} with content notes are hidden (<a href="#prefs" style="text-decoration:underline">settings</a>).</span>` : ""}</p>
      </div>
      ${inProgress.length ? section("Continue watching", rowOf(inProgress), "#history", "Pick up where you left off. Positions are saved in this browser.") : ""}
      ${myCourses.length ? section("Your courses", `<div class="row">${myCourses.map(([sd]) => seriesCard(sd)).join("")}</div>`, "#courses", "Courses you've started, most recent first.") : ""}
      ${section(state.history.length ? "For you" : "Start here", rowOf(fy), null, state.history.length ? "Based on what you've watched here. Nothing leaves your browser." : "A fresh mix every day, one video per topic.")}
      ${teachSection()}
      ${courseRow.length ? section("Courses", `<div class="row">${courseRow.map(sd => seriesCard(sd)).join("")}</div>`, "#courses", `Taught courses and lecture series, every lecture in order, as the institutions published them: ${KINDS.course} courses and ${KINDS.series} series. Seminars and conference talks have their own shelf on the Courses page.`) : ""}
      ${section("The canon", rowOf(canon), "#canon", "The most vouched-for videos across all communities.")}
      ${shelfRows}
      ${!courseRow.length && PT.series.length ? section("Courses & series", `<div class="row">${PT.series.slice(0, 8).map(sd => seriesCard(sd)).join("")}</div>`, "#courses", "Full lecture series people recommend whole.") : ""}
      ${section("Recently recommended", rowOf(recent), null, "Vouched for in 2024 or later.")}
      ${areaRows}
      ${care.length ? section("Handle with care", rowOf(care), "#care", "Popular videos built on findings that later shrank, failed to replicate or were overstated. Watch, then read the note.") : ""}
      ${section("Over an hour", rowOf(longs), "#longs", "Full lectures, long interviews and documentaries.")}
    `;
    wireTeach();
  }
  const KIND_WORD = { course: "lecture", series: "lecture", talks: "talk" };
  function seriesCard(sd) {
    const first = byId.get(sd.vids[0]);
    const sp = seriesProgress(sd);
    const done = sp.done;
    const unit = KIND_WORD[sd.kind] || "lecture";
    const lecturerCh = sd.inst === LECTURER_GROUP;
    const who = sd.inst ? [sd.lecturer, lecturerCh && sd.affil ? sd.affil : null, sd.year].filter(Boolean).join(", ") || sd.ch : first.ch;
    const chipText = lecturerCh ? "Lecturer's channel" : (sd.short || sd.inst);
    const chipTitle = lecturerCh ? `Published on ${sd.lecturer ? sd.lecturer + "'s" : "the lecturer's"} own channel${sd.affil ? ` · ${sd.affil}` : ""}${sd.ok === false ? " (affiliation not verified)" : sd.verified ? " (affiliation verified)" : ""}` : `${sd.inst}${sd.unit ? " · " + sd.unit : ""}`;
    const ph = sd.inst ? `<div class="ph lec" style="--h:${hueOf(sd.id)}" aria-hidden="true"><b>${sd.n}</b><span>${esc(lecturerCh ? (sd.lecturer || "lecturer") : (sd.short || sd.inst))}</span></div>` : "";
    const tail = sp.started ? `<span class="n">${done}/${sd.n}</span> watched · ${sp.pct}%${sp.leftSec && sp.pct < 100 ? ` · ${fmtLen(sp.leftSec)} left` : ""}` : sd.inst ? `<span class="chip inst ${sd.ok === false ? "unverified" : ""}" title="${esc(chipTitle)}">${esc(chipText)}</span>${sd.ok === false ? `<span class="faint">not verified</span>` : sd.vouched ? `<span class="faint">${sd.vouched} vouched</span>` : ""}` : sd.topics.map(t => `<span class="chip">${esc(topics.get(t) ? topics.get(t).name : t)}</span>`).join("");
    return `<a class="card course" href="#s-${sd.id}" data-id="${first.id}"><div class="thumb">${ph}${img(first.id)}<span class="tag series">${sd.n} ${unit}s${sd.hours >= 1 ? ` · ${Math.round(sd.hours)} h` : ""}</span>${sp.started && sp.pct < 100 ? `<i class="prog" style="width:${sp.pct}%"></i>` : ""}${sp.pct >= 100 ? `<span class="done-badge" title="Course finished">✓</span>` : ""}</div><div class="body"><div class="title">${esc(sd.name)}</div><div class="ch">${esc(who || "")}</div><div class="vouch">${tail}</div></div></a>`;
  }

  function listPage(opts) {
    // generic sortable/filterable grid page
    setNav(opts.nav || ""); setTitle(opts.title);
    const params = opts.params || {};
    const sort = params.sort || "vouched";
    const dur = params.dur || "any";
    const type = params.type || "any";
    const src = params.src || "any";
    let list = opts.list.slice();
    const isTalk = v => { const sd = v.series ? series.get(v.series) : null; return (sd && sd.kind === "talks") || (v.inst && v.inst.loose && v.type !== "lecture"); };
    if (src === "vouched") list = list.filter(v => v.nrec > 0);
    if (src === "course") list = list.filter(v => v.inst && !isTalk(v));          // taught courses and lecture series only
    if (src === "talks") list = list.filter(v => v.inst && isTalk(v));            // seminars, grand rounds, conference talks
    if (sort === "score") list.sort((a, b) => ((b.cscore != null ? b.cscore : b.score) - (a.cscore != null ? a.cscore : a.score)) || (b.score - a.score));
    if (dur === "short") list = list.filter(v => v.len && v.len < 20 * 60);
    if (dur === "medium") list = list.filter(v => v.len >= 20 * 60 && v.len < 60 * 60);
    if (dur === "long") list = list.filter(v => v.len >= 3600);
    if (type !== "any") list = list.filter(v => (v.type || "other") === type);
    if (sort === "newest") list.sort((a, b) => (b.pub || "").localeCompare(a.pub || ""));
    if (sort === "recent") list.sort((a, b) => (b.last - a.last) || (b.score - a.score));
    if (sort === "shortest") list.sort((a, b) => (a.len || 1e9) - (b.len || 1e9));
    if (sort === "longest") list.sort((a, b) => (b.len || 0) - (a.len || 0));
    const types = [...new Set(opts.list.map(v => v.type).filter(Boolean))].sort();
    const link = (k, val) => `#${opts.path}?${new URLSearchParams({ ...params, [k]: val }).toString()}`;
    const seg = (k, cur, items) => `<div class="seg" role="group" aria-label="${SEG_LABEL[k] || k}">${items.map(([val, label]) => `<a href="${link(k, val)}" aria-current="${cur === val}" class="segbtn">${label}</a>`).join("")}</div>`;
    main.innerHTML = `
      <h1>${opts.title}</h1>
      ${opts.intro ? `<p class="lede">${opts.intro}</p>` : ""}
      ${opts.extra || ""}
      <div class="toolbar">
        ${seg("sort", sort, [["vouched", "Legitimacy first"], ["score", "Most vouched"], ["recent", "Recently recommended"], ["newest", "Newest upload"], ["shortest", "Shortest"], ["longest", "Longest"]])}
        ${opts.list.some(v => v.inst) && opts.list.some(v => v.nrec) ? seg("src", src, [["any", "All"], ["vouched", "Community-vouched"], ["course", "Course lectures"], ["talks", "Seminars & talks"]]) : ""}
        ${seg("dur", dur, [["any", "Any length"], ["short", "Under 20 min"], ["medium", "20–60 min"], ["long", "Over 1 h"]])}
        ${types.length > 1 ? `<select class="btn" id="typeSel" aria-label="Type"><option value="any">Any type</option>${types.map(t => `<option value="${t}" ${t === type ? "selected" : ""}>${t}</option>`).join("")}</select>` : ""}
        <span class="faint">${plural(list.length, "video")}</span>
      </div>
      ${list.length ? paged(list) : `<div class="empty"><h2>Nothing matches these filters</h2><p>Try another length or type.</p></div>`}`;
    wireMore(list);
    const sel = document.getElementById("typeSel");
    if (sel) sel.onchange = () => { location.hash = link("type", sel.value); };
  }

  function pageTopic(id, params) {
    const t = topics.get(id); if (!t) return notFound();
    const a = areaOf.get(id);
    const list = V.filter(v => v.topics.includes(id) && visible(v)).sort((x, y) => (x.topics[0] === id ? 0 : 1) - (y.topics[0] === id ? 0 : 1) || byLegitimacy(x, y));
    const siblings = a.topics.map(s => `<a class="tpill ${s.id === id ? "active" : ""}" href="#t-${s.id}">${esc(s.name)} <span class="faint">${s.n}</span></a>`).join("");
    listPage({ nav: "topics", title: esc(t.name), intro: esc(t.desc), path: `t-${id}`, params, list, extra: `<div class="topic-pills">${siblings}</div>` });
  }
  function pageArea(id, params) {
    const a = areas.find(x => x.id === id); if (!a) return notFound();
    const ids = new Set(a.topics.map(t => t.id));
    const list = V.filter(v => visible(v) && v.topics.some(t => ids.has(t)));
    const pills = a.topics.map(s => `<a class="tpill" href="#t-${s.id}">${esc(s.name)} <span class="faint">${s.n}</span></a>`).join("");
    listPage({ nav: "topics", title: esc(a.name), path: `a-${id}`, params, list, extra: `<div class="topic-pills">${pills}</div>` });
  }
  function pageTopics() {
    setNav("topics"); setTitle("Topics");
    main.innerHTML = `<h1>Topics</h1><p class="lede">${topics.size} topics in ${areas.length} areas. Counts include videos filed under more than one topic.</p>
      <div class="areas">${areas.map(a => `<div class="area"><h2><a href="#a-${a.id}">${esc(a.name)}</a></h2><ul>${a.topics.map(t => `<li><a href="#t-${t.id}"><span>${esc(t.name)}</span><span class="n">${t.n}</span></a></li>`).join("")}</ul></div>`).join("")}</div>`;
  }
  function pageCourses(params) {
    setNav("courses"); setTitle("Courses");
    const p = params || {};
    const shelf = p.shelf || "courses", level = p.level || "any";
    const isFormal = sd => sd.kind !== "talks";
    const all = PT.series.filter(sd => sd.inst);
    const shelfSeries = all.filter(sd => (shelf === "talks" ? !isFormal(sd) : shelf === "all" ? true : isFormal(sd)) && (level === "any" || sd.level === level));
    const vouchedSeries = PT.series.filter(sd => !sd.inst);
    const byInst = new Map();
    for (const sd of shelfSeries) { const a = byInst.get(sd.inst) || []; a.push(sd); byInst.set(sd.inst, a); }
    const rank = list => list.reduce((a, sd) => a + sd.pop, 0) + 0.01 * list.reduce((a, sd) => a + sd.n, 0);
    // institutions by weight; lecturers' own channels as one group after them, its verified collections before the unverified
    const groups = [...byInst.entries()].sort((a, b) => ((a[0] === LECTURER_GROUP) - (b[0] === LECTURER_GROUP)) || (rank(b[1]) - rank(a[1])));
    for (const [name, list] of groups) if (name === LECTURER_GROUP) list.sort((a, b) => ((a.ok === false) - (b.ok === false)) || (b.pop - a.pop) || (b.n - a.n));
    const groupName = name => name === LECTURER_GROUP ? "Lecturers' own channels" : name;
    const groupSub = (name, list) => {
      const units = [...new Set(list.map(sd => sd.unit).filter(Boolean))];
      if (name === LECTURER_GROUP) { const nv = list.filter(sd => sd.ok !== false).length; return `Courses published on a lecturer's own channel, not the university's. ${nv} of ${list.length} with an affiliation an institutional page confirms; the rest say so.`; }
      return units.length ? `${units.slice(0, 4).join(" · ")}${units.length > 4 ? ` · ${units.length - 4} more` : ""}` : "";
    };
    const s = PT.stats.inst || { courses: 0, lectures: 0, institutions: 0, also_vouched: 0 };
    const nFormal = all.filter(isFormal).length, nTalks = all.length - nFormal;
    const link = (k, val) => `#courses?${new URLSearchParams({ ...p, [k]: val }).toString()}`;
    const seg = (k, cur, items) => `<div class="seg" role="group" aria-label="${SEG_LABEL[k] || k}">${items.map(([val, label]) => `<a href="${link(k, val)}" aria-current="${cur === val}" class="segbtn">${label}</a>`).join("")}</div>`;
    const lectures = shelfSeries.reduce((a, sd) => a + sd.n, 0);
    const shelfNote = shelf === "talks"
      ? `<b>Seminars, grand rounds and conference sessions.</b> Recorded talks that departments, institutes and societies publish: a research seminar series, a hospital's psychiatry grand rounds, the sessions of an annual meeting. They are institutional but <b>not a course and not peer-reviewed</b> — a speaker's own account of their work, often preliminary. Good for seeing where a field is right now; weigh them accordingly.`
      : shelf === "all" ? `Everything in the institutional tier, taught courses and recorded talks together.`
      : `<b>Taught courses and lecture series.</b> A full term of a university course, or a lecture series on one theme, exactly as the institution published it — every lecture, in order.`;
    main.innerHTML = `<h1>Courses</h1>
      <p class="lede">${s.courses ? `<b>${s.lectures.toLocaleString()}</b> lectures in <b>${s.courses.toLocaleString()}</b> courses and lecture collections, published by <b>${s.institutions}</b> universities, research institutes, societies and clinical institutions. Every lecture is here, in order, because the institution put it online — institutional backing instead of a vouch count. Where a community also vouched for a lecture, the card says so (${s.also_vouched} lectures so far). Your progress is remembered in this browser.` : "Lecture series where several lectures were recommended, grouped by channel. Your progress is remembered in this browser."}</p>
      ${s.courses ? `<div class="toolbar">${seg("shelf", shelf, [["courses", `Courses <span class="n">${nFormal}</span>`], ["talks", `Seminars & conferences <span class="n">${nTalks}</span>`], ["all", "Everything"]])}${seg("level", level, [["any", "Any level"], ["intro", "Intro"], ["advanced", "Advanced"], ["public", "Public lectures"]])}</div>
      <p class="shelf-note">${shelfNote}${(PT.pathways || []).length && shelf !== "talks" ? ` <a href="#pathways" style="text-decoration:underline">Not sure where to start? Pathways.</a>` : ""}</p>
      <div class="toolbar"><label class="filter"><input id="courseFilter" type="search" placeholder="Filter by institution, course or lecturer" aria-label="Filter courses" spellcheck="false"></label><span class="faint" id="courseCount">${plural(shelfSeries.length, "collection")}, ${plural(lectures, "lecture")}, ${groups.length} institutions</span></div>` : ""}
      <div id="courseGroups">${groups.map(([name, list]) => `<section class="section inst-group" data-inst="${esc(name.toLowerCase())}"><div class="section-head"><div><h2>${esc(groupName(name))}</h2><div class="sub">${plural(list.length, shelf === "talks" ? "collection" : "course")} · ${plural(list.reduce((a, sd) => a + sd.n, 0), shelf === "talks" ? "talk" : "lecture")} · ${Math.round(list.reduce((a, sd) => a + sd.hours, 0))} hours${name !== LECTURER_GROUP && list[0].ch ? ` · published by ${esc([...new Set(list.map(sd => sd.ch))].slice(0, 3).join(", "))}` : ""}${groupSub(name, list) ? `<br>${esc(groupSub(name, list))}` : ""}</div></div></div><div class="grid">${list.map(sd => `<div class="cwrap" data-text="${esc((sd.name + " " + (sd.lecturer || "") + " " + (sd.affil || "") + " " + sd.inst + " " + (sd.unit || "") + " " + (sd.ch || "")).toLowerCase())}">${seriesCard(sd)}</div>`).join("")}</div></section>`).join("")}</div>
      ${!groups.length && s.courses ? `<div class="empty"><h2>Nothing matches these filters</h2></div>` : ""}
      ${vouchedSeries.length && shelf !== "talks" ? `<section class="section"><div class="section-head"><div><h2>Series people recommend piece by piece</h2><div class="sub">Channels where several lectures were vouched for individually; not complete courses.</div></div></div><div class="grid">${vouchedSeries.map(sd => seriesCard(sd)).join("")}</div></section>` : ""}`;
    const fi = document.getElementById("courseFilter");
    if (fi) {
      const apply = () => {
        const q = fi.value.trim().toLowerCase();
        let shown = 0, insts = 0;
        main.querySelectorAll(".inst-group").forEach(sec => {
          const instHit = !q || sec.dataset.inst.includes(q);
          let any = 0;
          sec.querySelectorAll(".cwrap").forEach(w => { const hit = instHit || w.dataset.text.includes(q); w.hidden = !hit; if (hit) any++; });
          sec.hidden = !any; if (any) { insts++; shown += any; }
        });
        document.getElementById("courseCount").textContent = q ? `${plural(shown, "collection")} match · ${insts} institutions` : `${plural(shelfSeries.length, "collection")}, ${plural(lectures, "lecture")}, ${groups.length} institutions`;
      };
      fi.oninput = apply;
    }
  }
  function pageSeries(id) {
    const sd = series.get(id); if (!sd) return notFound();
    setNav("courses"); setTitle(sd.name);
    const vids = sd.vids.map(i => byId.get(i)).filter(Boolean);
    const sp = seriesProgress(sd);
    const next = byId.get(nextInSeriesFor(sd)) || vids[0];
    const watched = sp.done;
    const unit = KIND_WORD[sd.kind] || "lecture";
    const nextAt = resumeAt(next);
    const lecturerCh = sd.inst === LECTURER_GROUP;
    const meta = sd.inst ? [sd.lecturer, lecturerCh && sd.affil ? sd.affil : null, sd.year, sd.level === "intro" ? "introductory" : sd.level === "advanced" ? "advanced" : sd.level === "public" ? "public lectures" : "", `${plural(vids.length, unit)}${sd.total > vids.length ? ` of the playlist's ${sd.total}` : ""}`, sd.hours >= 1 ? `${Math.round(sd.hours)} hours` : ""].filter(Boolean) : [];
    // what is not listed, and why: other channels' videos re-listed in the playlist are not the institution's; the rest were dropped as off-topic, promos or duplicates
    const missing = sd.total > vids.length ? (sd.cross ? `${sd.partial ? "Mostly a watch list: only the " + plural(vids.length, unit) + " on the institution's own channels are listed; the other " : "Not listed: "}${plural(sd.cross, "video")} in the playlist ${sd.cross === 1 ? "is" : "are"} other channels' uploads, not the institution's own${sd.total - vids.length - sd.cross > 0 ? `, and ${sd.total - vids.length - sd.cross} more ${sd.total - vids.length - sd.cross === 1 ? "was" : "were"} left out as off-topic, promos or duplicates` : ""}.` : `${sd.total - vids.length} of the playlist's videos ${sd.total - vids.length === 1 ? "was" : "were"} left out as off-topic, promos or duplicates.`) : "";
    const publisherLine = lecturerCh
      ? `Published on ${sd.lecturer ? esc(sd.lecturer) + "'s" : "the lecturer's"} own channel${sd.ch && sd.ch !== sd.lecturer ? ` (${esc(sd.ch)})` : ""}, not a university's. ${sd.affil ? (sd.verified ? `${esc(sd.lecturer || "The lecturer")} teaches at ${esc(sd.affil)} — an institutional page confirms it.` : `The channel says ${esc(sd.lecturer || "the lecturer")} teaches at ${esc(sd.affil)}; <b>no institutional page confirms it</b>, so this collection ranks with independent long-form talks, not with the institutions.`) : `<b>No affiliation could be verified</b>, so this collection ranks with independent long-form talks, not with the institutions.`}`
      : sd.ok === false ? `<b>Publisher not verified:</b> ${esc(sd.pubwhy || "the channel's standing could not be established")}. This collection ranks with independent long-form talks, not with the institutions.` : "";
    main.innerHTML = `<div class="course-head">
      ${sd.inst ? `<div class="eyebrow"><span class="chip inst ${sd.ok === false ? "unverified" : ""}">${esc(lecturerCh ? "Lecturer's own channel" : sd.inst)}</span>${sd.unit && !lecturerCh ? ` <span class="muted">${esc(sd.unit)}</span> ·` : ""} ${sd.kind === "talks" ? "talk collection" : sd.kind === "series" ? "lecture series" : "complete course"}</div>` : ""}
      <h1>${esc(sd.name)}</h1>
      ${sd.inst ? `<p class="lede">${sd.note ? esc(sd.note) + " " : ""}<span class="muted">${meta.map(esc).join(" · ")}.</span>${sd.vouched ? ` <span class="muted">${sd.vouched === vids.length ? "Every" : sd.vouched} ${sd.vouched === 1 ? unit + " was" : unit + "s were"} also vouched for by the communities.</span>` : ""}${missing ? ` <span class="muted">${missing}</span>` : ""}</p>${publisherLine ? `<p class="shelf-note">${publisherLine}</p>` : ""}` : `<p class="lede">${plural(vids.length, "lecture")} people recommended from this series.</p>`}
      ${sp.started ? `<div class="course-progress"><div class="bar" role="progressbar" aria-label="Course progress" aria-valuenow="${sp.pct}" aria-valuemin="0" aria-valuemax="100"><i style="width:${sp.pct}%"></i></div><span>${sp.pct >= 100 ? `Finished — all ${sp.n} ${unit}s` : `${sp.done} of ${sp.n} ${unit}s watched · ${sp.pct}%${sp.leftSec ? ` · about ${fmtLen(sp.leftSec)} left` : ""}`}</span></div>` : ""}
      <div class="toolbar"><a class="btn primary" href="#v-${next.id}">${sp.pct >= 100 ? "Watch again" : sp.started ? "Continue" : "Start"}: ${esc(next.title.slice(0, 60))}${nextAt ? ` <span class="faint">from ${fmtDur(nextAt)}</span>` : ""}</a>${sd.readings ? `<a class="btn quiet" href="${esc(sd.readings)}" target="_blank" rel="noopener">Syllabus &amp; readings ↗</a>` : ""}${sd.url ? `<a class="btn quiet" href="${esc(sd.url)}" target="_blank" rel="noopener">${sd.provider === "panopto" ? "Course on Panopto" : sd.provider === "archive" ? "Course on the Internet Archive" : "Playlist on YouTube"} ↗</a>` : ""}${sd.chid || next.chid ? `<a class="btn quiet" href="https://www.youtube.com/channel/${esc(sd.chid || next.chid)}" target="_blank" rel="noopener">${esc(sd.ch || next.ch || "Channel")} ↗</a>` : ""}${sd.topics.map(t => `<a class="chip" href="#t-${t}">${esc(topics.get(t) ? topics.get(t).name : t)}</a>`).join("")}</div></div>
      ${pathwaysFor(id).map(({ pw, i }) => { const prev = i > 0 ? stepTarget(pw.steps[i - 1]) : null, nxt = i + 1 < pw.steps.length ? stepTarget(pw.steps[i + 1]) : null; return `<p class="pathline">Step ${i + 1} of ${pw.steps.length} in the <a href="#pathways?p=${esc(pw.id)}">${esc(pw.name)}</a> pathway${prev ? ` · before it: <a href="${prev.href}">${esc(prev.name)}</a>` : ""}${nxt ? ` · after it: <a href="${nxt.href}">${esc(nxt.name)}</a>` : ""}</p>`; }).join("")}
      <ol class="lectures">${vids.map((v, i) => `<li class="${isDone(v.id) ? "done" : ""}" data-row="${v.id}"><span class="num">${isDone(v.id) ? "✓" : sd.inst ? v.inst.i : i + 1}</span><a class="thumb ${isDone(v.id) ? "is-done" : ""}" href="#v-${v.id}" aria-label="${esc(v.title)}">${sd.inst && !thumbUrl(v.id) ? `<div class="ph lec" style="--h:${hueOf(sd.id)}" aria-hidden="true"><b>${v.inst.i}</b></div>` : ""}${img(v.id)}${v.len ? `<span class="pill">${fmtDur(v.len)}</span>` : ""}${progressBar(v)}</a><div><a class="lt" href="#v-${v.id}">${esc(v.title)}</a>${v.why || (v.summary && !sd.inst) ? `<div class="muted" style="font-size:13.5px">${esc(v.why || v.summary)}</div>` : ""}${v.nrec ? vouchLine(v) : sd.inst ? `<div class="vouch"><span class="faint">${v.len ? fmtLen(v.len) : ""}${v.topics[0] && v.topics[0] !== sd.topics[0] ? ` · ${esc(topics.get(v.topics[0]).name)}` : ""}</span></div>` : ""}<div class="track">${isDone(v.id) ? `<span class="watched">Watched</span>` : pctOf(v) ? `<span class="muted">${pctOf(v)}% · <a href="#v-${v.id}">resume at ${fmtDur(resumeAt(v) || progOf(v.id).t)}</a></span>` : ""}<button class="mini" data-done="${v.id}">${isDone(v.id) ? "Mark unwatched" : "Mark watched"}</button></div></div></li>`).join("")}</ol>`;
    main.querySelectorAll("[data-done]").forEach(b => b.onclick = () => { markDone(b.dataset.done, !isDone(b.dataset.done)); pageSeries(id); });
  }
  function pageClips() {
    setNav("clips"); setTitle("Clips");
    const list = V.filter(v => visible(v) && v.clips && v.clips.length);
    main.innerHTML = `<h1>Clips</h1><p class="lede">Moments people linked to directly, with a timestamp. Psychology people point at the specific minute.</p>
      ${list.map(v => `<div class="card row-item"><a class="thumb" href="#v-${v.id}?t=${v.clips[0]}" aria-label="${esc(v.title)}">${thumbInner(v)}</a><div><a class="title" href="#v-${v.id}">${esc(v.title)}</a><div class="ch">${esc(v.ch)}</div><div class="clips" style="margin-top:8px">${v.clips.map(t => { const vo = v.vouches.find(x => x.t === t); return `<a class="btn quiet" style="font-size:13px" href="#v-${v.id}?t=${t}"><b style="color:var(--amber)">${fmtDur(t)}</b>${vo ? ` <span class="muted">${esc(vo.q.slice(0, 90))}${vo.q.length > 90 ? "…" : ""}</span>` : ""}</a>`; }).join("")}</div></div></div>`).join("") || `<div class="empty"><h2>No clips yet</h2></div>`}`;
  }
  function pageCare(params) {
    setNav("care"); setTitle("Replication notes");
    const p = params || {}; const want = p.status || "all";
    const groups = new Map();
    for (const v of V) if (v.badge) { const g = groups.get(v.badge.id) || { promotes: [], critique: [], source: [] }; g[v.badge.role === "critique" ? "critique" : v.badge.role === "source" ? "source" : "promotes"].push(v); groups.set(v.badge.id, g); }
    const ORDER = ["failed", "myth", "misreported", "reversed", "overstated", "smaller", "mixed", "fraud", "replicated"];
    const ids = Object.keys(PT.contested).filter(id => want === "all" || statusOf(id) === want)
      .sort((a, b) => { const sa = ORDER.indexOf(statusOf(a)), sb = ORDER.indexOf(statusOf(b)); if (sa !== sb) return sa - sb; const na = groups.has(a) ? groups.get(a).promotes.length + groups.get(a).critique.length + groups.get(a).source.length : 0; const nb = groups.has(b) ? groups.get(b).promotes.length + groups.get(b).critique.length + groups.get(b).source.length : 0; return nb - na || a.localeCompare(b); });
    const counts = {}; for (const id of Object.keys(PT.contested)) counts[statusOf(id)] = (counts[statusOf(id)] || 0) + 1;
    const link = val => `#care?${new URLSearchParams({ ...p, status: val }).toString()}`;
    const seg = `<div class="seg" role="group" aria-label="Replication status"><a href="#care" aria-current="${want === "all"}" class="segbtn">All <span class="n">${Object.keys(PT.contested).length}</span></a>${ORDER.filter(st => counts[st]).map(st => `<a href="${link(st)}" aria-current="${want === st}" class="segbtn">${esc(STATUS_LABELS[st] || st)} <span class="n">${counts[st]}</span></a>`).join("")}</div>`;
    const paperLine = pp => `<li>${esc(pp.cite)}${pp.doi ? ` <a href="https://doi.org/${esc(pp.doi)}" target="_blank" rel="noopener">doi:${esc(pp.doi)}</a>` : pp.url ? ` <a href="${esc(pp.url)}" target="_blank" rel="noopener">link ↗</a>` : ""}</li>`;
    main.innerHTML = `<h1>Replication notes</h1><p class="lede">Psychology's most-shared videos include some of its least reliable findings — and some of its sturdiest. Every finding here has a replication status and the papers behind it, so you can watch the classic and then read what happened next. The notes are PsychTube's, not the communities'; the status is a summary of the sources listed, not a verdict on a whole field.</p>
      <div class="toolbar">${seg}</div>
      ${ids.map(id => { const c = PT.contested[id]; const g = groups.get(id) || { promotes: [], critique: [], source: [] }; return `<section class="section care-list" id="care-${esc(id)}"><div class="section-head"><div><h2>${esc(c.name)} ${statusChip(id)}</h2><div class="sub" style="max-width:80ch;color:var(--ink-2)">${esc(c.note)}</div>${c.sources && c.sources.length ? `<ul class="papers sub">${c.sources.map(paperLine).join("")}</ul>` : `<div class="sub faint">${esc(c.source)}</div>`}</div></div>${g.source.length ? `<h3 class="care-h">The original</h3>${grid(g.source)}` : ""}${g.promotes.length ? `${g.source.length ? `<h3 class="care-h">Videos that present it</h3>` : ""}${grid(g.promotes)}` : ""}${g.critique.length ? `<h3 class="care-h" style="color:var(--mint)">The pushback</h3>${grid(g.critique)}` : ""}${!g.source.length && !g.promotes.length && !g.critique.length ? `<p class="faint">No video in the catalog is tagged with this finding yet.</p>` : ""}</section>`; }).join("")}`;
    if (p.f) requestAnimationFrame(() => { const el = document.getElementById("care-" + p.f); if (el) el.scrollIntoView(); });   // after the router's scrollTo(0, 0)
  }
  // ------------------------------------------------------------ pathways (quiet side feature: ordered routes through the courses)
  const PATHWAYS = PT.pathways || [];
  const stepTarget = st => st.series ? { href: `#s-${st.series}`, name: (series.get(st.series) || {}).name || st.series, sub: (series.get(st.series) || {}).inst || "" }
    : st.all ? { href: `#s-${st.all[0]}`, name: `${st.label} (${st.all.length} courses, in order)`, sub: (series.get(st.all[0]) || {}).inst || "", multi: true }
    : st.shelf ? { href: `#shelf-${st.shelf}`, name: ((PT.shelves || []).find(x => x.id === st.shelf) || {}).name || st.shelf, sub: "a PsychTube shelf" }
    : st.page ? { href: `#${st.page}`, name: st.page_label || st.page, sub: "a PsychTube page" } : null;
  const pathwaysFor = sid => { const out = []; for (const pw of PATHWAYS) pw.steps.forEach((st, i) => { if (st.series === sid || (st.all || []).includes(sid)) out.push({ pw, i }); }); return out; };
  const pathStepDone = st => { const ids = st.series ? [st.series] : st.all || []; return ids.length && ids.every(id => { const sd = series.get(id); return sd && seriesProgress(sd).pct >= 100; }); };
  function pagePathways(params) {
    setNav("courses"); setTitle("Pathways");
    const want = (params || {}).p;
    const one = want && PATHWAYS.find(pw => pw.id === want);
    const render = pw => `<section class="section pathway" id="pw-${esc(pw.id)}"><div class="section-head"><div><h2><a href="#pathways?p=${esc(pw.id)}">${esc(pw.name)}</a></h2><div class="sub">${esc(pw.for)}</div></div></div>
      <ol class="path">${pw.steps.map((st, i) => { const t = stepTarget(st); if (!t) return ""; const done = pathStepDone(st); return `<li class="${done ? "done" : ""}"><span class="num">${done ? "✓" : i + 1}</span><div><div class="plabel">${esc(st.label)}</div>${t.multi ? `<span class="ptarget">${esc(t.sub || "")}</span>` : `<a class="ptarget" href="${t.href}">${esc(t.name)}</a>${t.sub ? `<span class="faint"> · ${esc(t.sub)}</span>` : ""}`}${st.all ? `<div class="faint" style="margin-top:4px">${st.all.map(id => `<a href="#s-${esc(id)}" style="text-decoration:underline">${esc(((series.get(id) || {}).name || id).replace(/^CNS/, "CNS "))}</a>`).join(" → ")}</div>` : ""}<p class="pwhy">${esc(st.why)}</p></div></li>`; }).join("")}</ol></section>`;
    main.innerHTML = `<h1>Pathways</h1>
      <p class="lede">Suggested orders through the courses, for people who want a prerequisite chain rather than a catalog. Each is one reasonable route, not the only one: a first course, the course that assumes it, the primary sources, then the seminars where the field talks to itself. ${one ? `<a href="#pathways" style="text-decoration:underline">All ${PATHWAYS.length} pathways</a>.` : ""}</p>
      ${(one ? [one] : PATHWAYS).map(render).join("")}
      ${!PATHWAYS.length ? `<div class="empty"><p>No pathways in this build.</p></div>` : ""}`;
  }
  function pageShelf(id) {
    const sh = (PT.shelves || []).find(x => x.id === id); if (!sh) return notFound();
    setNav(id); setTitle(sh.name);
    const paperLine = pp => pp ? `<li>${esc(pp.cite)}${pp.doi ? ` <a href="https://doi.org/${esc(pp.doi)}" target="_blank" rel="noopener">doi:${esc(pp.doi)}</a>` : pp.url ? ` <a href="${esc(pp.url)}" target="_blank" rel="noopener">link ↗</a>` : ""}</li>` : "";
    const withVideo = sh.items.filter(it => it.vid && byId.has(it.vid)).length;
    main.innerHTML = `<h1>${esc(sh.name)}</h1><p class="lede">${esc(sh.tagline)}</p>
      <p class="shelf-note">${withVideo} of ${sh.items.length} have a copy from the rights holder, the institution or an archive; the rest are listed with the paper and a note on where the film lives, rather than linking a re-upload. Each item says what it is as a record — the original footage, a documentary of the time, or a later report or talk — and whose copy is playing.</p>
      <ol class="shelf">${sh.items.map(it => { const v = it.vid ? byId.get(it.vid) : null; return `<li class="shelf-item${v ? "" : " novideo"}">
        <div class="shelf-media">${v ? card(v, { cls: "small", chips: 0 }) : `<div class="shelf-none"><b>No authorized copy online</b><span>${esc(it.uploader || "Listed for the paper and the record.")}</span></div>`}</div>
        <div class="shelf-text"><h2>${esc(it.title)}${it.year ? ` <span class="faint">${it.year}</span>` : ""}</h2>${it.people ? `<p class="people">${esc(it.people)}</p>` : ""}<p>${esc(it.what || "")}</p>
          <p class="whose">${it.form ? `<span class="form">${esc(it.form[0].toUpperCase() + it.form.slice(1))}</span>` : ""}${v ? ` · whose copy: ${esc(it.uploader || v.ch || "")}${it.legit === "relisted" ? ` <span class="faint">(a channel's video re-listed in an institution's playlist, not the institution's own upload)</span>` : it.legit === "archive" ? ` <span class="faint">(Internet Archive${it.rights ? "; " + esc(it.rights) : "; rights as stated on the item"})</span>` : ""}` : ""}</p>
          ${it.paper || it.paper2 ? `<ul class="papers">${paperLine(it.paper)}${paperLine(it.paper2)}</ul>` : ""}
          <div class="shelf-foot">${it.status ? `<a href="#care?status=${esc(statusOf(it.status))}&amp;f=${esc(it.status)}" class="status s-${esc(statusOf(it.status))}">${esc(statusLabel(it.status))}: ${esc(PT.contested[it.status].name)}</a>` : ""}${(it.alt || []).map(a => `<a href="${esc(a.url)}" target="_blank" rel="noopener" class="faint" style="text-decoration:underline">${esc(a.label)} ↗</a>`).join("")}${it.topics.map(t => topics.get(t) ? `<a class="chip" href="#t-${t}">${esc(topics.get(t).name)}</a>` : "").join("")}</div>
        </div></li>`; }).join("")}</ol>`;
  }
  function pageSimple(nav, title, intro, list, params, path) {
    listPage({ nav, title, intro, list, params, path });
  }
  function pageSearch(params) {
    const q = params.q || "";
    setNav(""); setTitle(`Search: ${q}`);
    document.getElementById("q").value = q;
    const res = search(q);
    const topicHits = [...topics.values()].filter(t => norm(t.name).includes(norm(q)) || norm(t.desc).includes(norm(q))).slice(0, 6);
    const nq = norm(q);
    const seriesHits = nq.length >= 3 ? PT.series.filter(sd => norm([sd.name, sd.lecturer, sd.inst, sd.short, sd.ch].join(" ")).includes(nq)).slice(0, 6) : [];
    main.innerHTML = `<h1>${res.length ? plural(res.length, "result") : "No results"} for “${esc(q)}”</h1>
      ${topicHits.length ? `<div class="topic-pills">${topicHits.map(t => `<a class="tpill" href="#t-${t.id}">${esc(t.name)} <span class="faint">${t.n}</span></a>`).join("")}</div>` : ""}
      ${seriesHits.length ? `<div class="row" style="margin-top:12px">${seriesHits.map(sd => seriesCard(sd)).join("")}</div>` : ""}
      ${res.length ? paged(res, { cls: "row-item", desc: true, chips: 4 }, `<div style="margin-top:14px" data-paged>`) : `<div class="empty"><p>Try a topic word (memory, Sapolsky, replication), a channel, or a person.</p></div>`}`;
    wireMore(res, { cls: "row-item", desc: true, chips: 4 });
  }

  // ------------------------------------------------------------ player controller (tracks position per provider)
  let player = null;                       // { stop(), seek(t), kind }
  const loadScript = (src, test, ms) => new Promise((res, rej) => { if (test()) return res(); const sc = document.createElement("script"); sc.src = src; sc.async = true; sc.onerror = () => rej(new Error("load failed")); document.head.appendChild(sc); const t0 = Date.now(); const tick = () => { if (test()) res(); else if (Date.now() - t0 > (ms || 8000)) rej(new Error("timeout")); else setTimeout(tick, 120); }; tick(); });
  function unmountPlayer() { if (player) { try { player.stop(); } catch (e) { /* ignore */ } player = null; } }
  function mountPlayer(v, start, onEnded) {
    unmountPlayer();
    const box = document.getElementById("playerBox"); if (!box) return;
    const autoplay = !!state.settings.autoplay;
    let lastSave = 0; let ticker = null; let ended = false;
    const record = (t, d, force) => { if (!(t > 0)) return; const now = Date.now(); if (!force && now - lastSave < 4000) return; lastSave = now; setProgress(v.id, t, d); };
    const finish = () => { if (ended) return; ended = true; markDone(v.id, true); if (onEnded) onEnded(); };
    const fallbackIframe = () => { box.innerHTML = `<iframe id="player" src="${embedUrl(v, start, autoplay)}" title="${esc(v.title)}" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share; fullscreen" allowfullscreen referrerpolicy="strict-origin-when-cross-origin"></iframe>`; player = { kind: "iframe", stop() {}, save() {}, seek(t) { document.getElementById("player").src = embedUrl(v, t, true); } }; };

    if (v.p === "archive" && v.f) {
      // the Internet Archive serves the MP4 itself, so a plain <video> gives exact positions
      box.innerHTML = `<video id="player" controls playsinline preload="metadata" poster="${thumbUrl(v)}" ${autoplay ? "autoplay" : ""} src="https://archive.org/download/${encodeURIComponent(v.id)}/${encodeURIComponent(v.f)}#t=${start || 0}"></video>`;
      const el = document.getElementById("player");
      el.addEventListener("timeupdate", () => record(el.currentTime, el.duration));
      el.addEventListener("pause", () => record(el.currentTime, el.duration, true));
      el.addEventListener("ended", () => { record(el.duration, el.duration, true); finish(); });
      player = { kind: "video", stop() { record(el.currentTime, el.duration, true); el.pause(); }, save() { record(el.currentTime, el.duration, true); }, seek(t) { el.currentTime = t; el.play().catch(() => {}); } };
      return;
    }
    if (v.p === "panopto") {
      box.innerHTML = `<div id="player"></div>`;
      loadScript("https://developers.panopto.com/scripts/embedapi.min.js", () => !!window.EmbedApi, 8000).then(() => {
        let api = null;
        const poll = () => { try { const t = api.getCurrentTime(); const d = api.getDuration(); if (t > 0) record(t, d); } catch (e) { /* not ready */ } };
        api = new window.EmbedApi("player", { width: "100%", height: "100%", serverName: v.host, sessionId: v.id,
          videoParams: { interactivity: "none", showtitle: false, showbrand: false, autoplay, start: start || 0, offerviewer: true },
          events: { onReady: () => { if (start) { try { api.seekTo(start); } catch (e) { /* ignore */ } } },
            onStateChange: st => { const S = window.PlayerState || {}; if (st === S.Playing) { clearInterval(ticker); ticker = setInterval(poll, 4000); } else { clearInterval(ticker); poll(); if (st === S.Ended) finish(); } } } });
        player = { kind: "panopto", stop() { clearInterval(ticker); poll(); }, save() { try { const t = api.getCurrentTime(); if (t > 0) record(t, api.getDuration(), true); } catch (e) { /* not ready */ } }, seek(t) { try { api.seekTo(t); api.playVideo && api.playVideo(); } catch (e) { fallbackIframe(); player.seek(t); } } };
      }).catch(fallbackIframe);
      return;
    }
    // YouTube via the IFrame API (positions, ended events); plain iframe if the API can't load
    box.innerHTML = `<div id="player"></div>`;
    loadScript("https://www.youtube.com/iframe_api", () => !!(window.YT && window.YT.Player), 8000).then(() => {
      let yt = null;
      const poll = () => { try { const t = yt.getCurrentTime(); const d = yt.getDuration(); if (t > 0) record(t, d); } catch (e) { /* not ready */ } };
      yt = new window.YT.Player("player", { host: "https://www.youtube-nocookie.com", videoId: v.id, width: "100%", height: "100%",
        playerVars: { start: start || 0, autoplay: autoplay ? 1 : 0, rel: 0, modestbranding: 1, playsinline: 1, origin: location.origin },
        events: { onStateChange: e => { const S = window.YT.PlayerState; if (e.data === S.PLAYING) { clearInterval(ticker); ticker = setInterval(poll, 4000); } else { clearInterval(ticker); if (e.data === S.PAUSED || e.data === S.BUFFERING) poll(); if (e.data === S.ENDED) { try { record(yt.getDuration(), yt.getDuration(), true); } catch (x) { /* ignore */ } finish(); } } },
          onError: () => { /* keep the frame; YouTube shows its own message */ } } });
      player = { kind: "youtube", stop() { clearInterval(ticker); poll(); try { yt.destroy(); } catch (e) { /* ignore */ } }, save() { try { const t = yt.getCurrentTime(); if (t > 0) record(t, yt.getDuration(), true); } catch (e) { /* not ready */ } }, seek(t) { try { yt.seekTo(t, true); yt.playVideo(); } catch (e) { /* ignore */ } } };
    }).catch(fallbackIframe);
  }
  const saveNow = () => { if (player && player.save) { try { player.save(); } catch (e) { /* ignore */ } } flushProgress(); };
  window.addEventListener("pagehide", saveNow);                                     // bfcache may bring the page back: keep the player
  document.addEventListener("visibilitychange", () => { if (document.hidden) saveNow(); });   // a backgrounded lecture keeps playing
  let upNextTimer = null;
  function showUpNext(v, sameSeries, nextId) {
    const el = document.getElementById("upnext"); if (!el) return;
    clearInterval(upNextTimer);
    if (!nextId) { el.hidden = false; el.innerHTML = `<div class="upnext-in"><b>Finished.</b> ${sameSeries ? `That was the last ${KIND_WORD[sameSeries.kind] || "lecture"} of <a href="#s-${sameSeries.id}">${esc(sameSeries.name)}</a>. ` : ""}<a href="#courses" style="text-decoration:underline">Browse courses</a></div>`; return; }
    const n = byId.get(nextId); if (!n) return;
    const auto = state.settings.autoNext === "auto";
    let left = 8;
    const render = () => { el.hidden = false; el.innerHTML = `<div class="upnext-in"><div><span class="faint">Finished ✓ · Up next${n.inst ? ` (${n.inst.i} of ${n.inst.of})` : ""}</span><div class="upnext-title">${esc(n.title)}</div></div><div class="upnext-actions"><a class="btn primary" id="upnextGo" href="#v-${nextId}">Play${auto && left > 0 ? ` in ${left}s` : ""}</a>${auto ? `<button class="btn quiet" id="upnextStay">Stay here</button>` : ""}</div></div>`; const stay = document.getElementById("upnextStay"); if (stay) stay.onclick = () => { clearInterval(upNextTimer); left = -1; render(); }; };
    render();
    if (auto) upNextTimer = setInterval(() => { if (left < 0) { clearInterval(upNextTimer); return; } left--; if (left === 0) { clearInterval(upNextTimer); location.hash = "#v-" + nextId; } else render(); }, 1000);
  }

  function pageWatch(id, params) {
    const v = byId.get(id); if (!v) return notFound();
    setNav(""); setTitle(v.title);
    const saved = resumeAt(v);
    const start = params.t != null ? (parseInt(params.t, 10) || 0) : saved;
    const resuming = params.t == null && saved > 0;
    // record history (newest first, unique)
    state.history = [{ id, ts: Date.now() }, ...state.history.filter(h => h.id !== id)].slice(0, 500);
    store.set("history", state.history);
    const rel = (v.rel || []).map(r => byId.get(r)).filter(Boolean).filter(visible);
    const sameTopic = V.filter(x => x.id !== id && visible(x) && x.topics[0] === v.topics[0] && !rel.includes(x)).slice(0, 10);
    const sameSeries = v.series ? series.get(v.series) : null;
    const posInSeries = sameSeries ? sameSeries.vids.indexOf(id) : -1;
    const nextInSeries = sameSeries ? sameSeries.vids[posInSeries + 1] : null;
    const c = v.badge ? PT.contested[v.badge.id] : null;
    const srcSummary = Object.entries(v.src).map(([s, n]) => `${n} on ${SRC_NAME[s]}`).join(", ");
    const paperLine = pp => pp ? `<li>${esc(pp.cite)}${pp.doi ? ` <a href="https://doi.org/${esc(pp.doi)}" target="_blank" rel="noopener">doi:${esc(pp.doi)}</a>` : pp.url ? ` <a href="${esc(pp.url)}" target="_blank" rel="noopener">link ↗</a>` : ""}</li>` : "";
    const o = v.orig;
    const shelfName = id => { const sh = (PT.shelves || []).find(x => x.id === id); return sh ? sh.name : id; };
    const origBox = o ? `<div class="box orig"><h2>${SHELF_HEAD[o.shelf] || "Primary source"}${o.year ? ` · ${o.year}` : ""}</h2>${o.people ? `<p class="people">${esc(o.people)}</p>` : ""}<p>${esc(o.what || "")}</p>${o.paper || o.paper2 ? `<h3>The paper</h3><ul class="papers">${paperLine(o.paper)}${paperLine(o.paper2)}</ul>` : ""}${o.alt && o.alt.length ? `<p class="faint">${o.alt.map(a => `<a href="${esc(a.url)}" target="_blank" rel="noopener" style="text-decoration:underline">${esc(a.label)} ↗</a>`).join(" · ")}</p>` : ""}<p class="faint" style="margin:0">${o.form ? `${esc(o.form[0].toUpperCase() + o.form.slice(1))} · ` : ""}${o.uploader ? `Copy: ${esc(o.uploader)}${o.legit === "official" ? " — the rights holder's or institution's own." : o.legit === "archive" ? ` — a library/archive collection${o.rights ? ` (${esc(o.rights)})` : ""}.` : o.legit === "relisted" ? " — a channel's video re-listed in an institution's playlist, not the institution's own upload." : ""} · ` : ""}<a href="#shelf-${esc(o.shelf)}" style="text-decoration:underline">All ${esc(shelfName(o.shelf).toLowerCase())}</a></p></div>` : "";
    const pubName = v.inst ? (v.inst.n === LECTURER_GROUP ? `${v.inst.u || "a lecturer"}'s own channel` : `${v.inst.n}${v.inst.u ? " · " + v.inst.u : ""}`) : "";
    const unverifiedNote = v.inst && v.inst.ok === false ? ` <b>${v.inst.n === LECTURER_GROUP ? "Affiliation not verified" : "Publisher not verified"}:</b> ${sameSeries && sameSeries.pubwhy ? esc(sameSeries.pubwhy) : sameSeries && sameSeries.affil ? `the channel says the lecturer teaches at ${esc(sameSeries.affil)}, and no institutional page confirms it` : "no institutional page ties this channel to a university or institute"}, so it ranks with independent long-form talks rather than with the institutions.` : "";
    const unlistedNote = v.unl ? ` <span class="muted">Unlisted on YouTube: it is reachable through the playlist, not from the channel page.</span>` : "";
    const looseBox = v.inst && v.inst.loose && !sameSeries ? `<div class="box inst"><h2>Published ${v.inst.n === LECTURER_GROUP ? "on" : "by"} ${esc(pubName)}</h2><p>A standalone ${v.type === "lecture" ? "lecture" : "talk"} on the institution's own channel, outside any course or series; put online by ${esc(v.ch || "")}. ${v.nrec ? "The communities below vouched for it on their own, too." : "It's here on the institution's authority, not a forum's: no community has vouched for this particular video."} <b>Not a course and not peer-reviewed:</b> a speaker's own account of their subject.${unverifiedNote}${unlistedNote}</p>${v.chid ? `<p class="faint" style="margin:0"><a href="https://www.youtube.com/channel/${esc(v.chid)}" target="_blank" rel="noopener" style="text-decoration:underline">${esc(v.ch || "Channel")} ↗</a></p>` : ""}</div>` : "";
    const instBox = v.inst && sameSeries ? `<div class="box inst"><h2>Published ${v.inst.n === LECTURER_GROUP ? "on" : "by"} ${esc(pubName)}</h2><p>${esc(KIND_WORD[sameSeries.kind] === "talk" ? "Talk" : "Lecture")} ${v.inst.i} of ${v.inst.of} in <a href="#s-${sameSeries.id}">${esc(sameSeries.name)}</a>${sameSeries.lecturer ? `, taught by ${esc(sameSeries.lecturer)}${sameSeries.affil && v.inst.n === LECTURER_GROUP ? ` (${esc(sameSeries.affil)}${sameSeries.verified ? "" : ", by the channel's own account"})` : ""}` : ""}${sameSeries.year ? ` (${sameSeries.year})` : ""}; put online by ${esc(v.ch || sameSeries.ch || "")}. ${v.nrec ? "The communities below vouched for this lecture on its own, too." : v.inst.n === LECTURER_GROUP ? "It's here because the lecturer published the whole course, not because a forum linked it." : "It's here on the institution's authority, not a forum's: no community has vouched for this particular lecture."}${sameSeries.kind === "talks" ? " <b>A recorded talk, not a course:</b> a speaker's own account of their work, as presented at a seminar, grand rounds or conference — not peer-reviewed." : ""}${unverifiedNote}${unlistedNote}${sameSeries.note ? ` <span class="muted">${esc(sameSeries.note)}</span>` : ""}</p><p class="faint" style="margin:0"><a href="#s-${sameSeries.id}" style="text-decoration:underline">${sameSeries.kind === "talks" ? "Whole collection" : "Whole course"}</a>${nextInSeries ? ` · <a href="#v-${nextInSeries}" style="text-decoration:underline">${sameSeries.kind === "talks" ? "Next talk" : "Next lecture"}</a>` : ""}${sameSeries.readings ? ` · <a href="${esc(sameSeries.readings)}" target="_blank" rel="noopener" style="text-decoration:underline">Syllabus &amp; readings ↗</a>` : ""}${sameSeries.url ? ` · <a href="${esc(sameSeries.url)}" target="_blank" rel="noopener" style="text-decoration:underline">${sameSeries.provider === "panopto" ? "Course on Panopto" : sameSeries.provider === "archive" ? "Course on the Internet Archive" : "Playlist on YouTube"} ↗</a>` : ""}</p></div>` : "";
    const groupsByComm = new Map();
    for (const vo of v.vouches) { const arr = groupsByComm.get(vo.c) || []; arr.push(vo); groupsByComm.set(vo.c, arr); }
    const vouchHtml = [...groupsByComm.entries()].map(([comm, arr]) => arr.map((vo, i) => `<li>
        <div class="who">${i === 0 ? `<b>${esc(comm === "Psychology & Neuroscience SE" ? "Psych SE" : comm)}</b>` : ""}${esc(vo.a || "")}${vo.d ? `<br>${esc(vo.d.slice(0, 4))}` : ""}<br><span class="stance ${esc(vo.k)}">${esc(stanceLabel(vo.k))}</span></div>
        <div class="what"><div class="q">${vo.q ? "“" + esc(vo.q) + "”" : ""}${vo.t ? ` <a href="#v-${id}?t=${vo.t}" class="faint">at ${fmtDur(vo.t)}</a>` : ""}</div>${vo.thread ? `<div class="thread">in “${esc(vo.thread)}”</div>` : ""}${vo.u ? `<div class="thread"><a href="${esc(vo.u)}" target="_blank" rel="noopener">Open the original ↗</a></div>` : ""}</div>
      </li>`).join("")).join("");
    main.innerHTML = `<div class="watch"><div>
      ${LINKOUT
        ? `<a class="player poster" href="${watchUrl(v, start)}" target="_blank" rel="noopener" aria-label="Watch on ${providerOf(v)}">${ART || v.p ? (thumbUrl(v) ? `<img src="${thumbUrl(v)}" alt="" onerror="this.style.visibility='hidden'">` : "") : `<img src="https://i.ytimg.com/vi/${id}/hq720.jpg" alt="" data-step="0" onload="window.__ptPoster(this,'${id}')" onerror="window.__ptPoster(this,'${id}',true)">`}<span class="play"><span class="play-ic">▶</span>Watch on ${providerOf(v)}${start ? ` from ${fmtDur(start)}` : ""}</span></a><p class="faint" style="margin:8px 0 0;font-size:13px">${FROM_DISK ? "YouTube's player won't run inside a page opened from disk, so this copy links out. " : "This hosted copy can't embed players, so it links out. "}For playback right here in the page, use the live site: <a href="${SITE_URL}#v-${id}" target="_blank" rel="noopener" style="text-decoration:underline">${SITE_URL.replace(/^https:\/\//, "")}</a></p>`
        : `<div class="player" id="playerBox"></div><div id="upnext" class="upnext" hidden></div>${resuming ? `<p class="faint resume-note">Resuming from ${fmtDur(start)} · <a href="#v-${id}?t=0" style="text-decoration:underline">start over</a></p>` : ""}`}
      <h1>${esc(v.title)}</h1>
      <div class="meta"><span>${esc(v.ch || "")}</span>${v.len ? `<span>${fmtLen(v.len)}</span>` : ""}${v.pub ? `<span>uploaded ${v.approx ? "around " : ""}${v.pub.slice(0, 4)}</span>` : ""}${v.views ? `<span>${v.approx ? "~" : ""}${fmtViews(v.views)}</span>` : ""}${v.inst && sameSeries ? `<a class="chip inst" href="#s-${sameSeries.id}">${esc(instShort(v.inst.n))} · ${esc(sameSeries.name.length > 40 ? sameSeries.name.slice(0, 38) + "…" : sameSeries.name)}</a>` : ""}${v.topics.map(t => `<a class="chip" href="#t-${t}">${esc(topics.get(t) ? topics.get(t).name : t)}</a>`).join("")}</div>
      <div class="actions">
        <button class="btn" id="likeBtn" aria-pressed="${state.liked.has(id)}">♥ ${state.liked.has(id) ? "Liked" : "Like"}</button>
        <button class="btn" id="laterBtn" aria-pressed="${state.later.has(id)}">${state.later.has(id) ? "In watch later" : "Watch later"}</button>
        ${LINKOUT ? "" : `<a class="btn quiet" href="${watchUrl(v, start)}" target="_blank" rel="noopener">Open on ${providerOf(v)} ↗</a>`}
        <button class="btn quiet" id="copyBtn">${LINKOUT ? `Copy ${providerOf(v)} link` : "Copy link"}</button>
        <button class="btn quiet" id="doneBtn" aria-pressed="${isDone(id)}">${isDone(id) ? "✓ Watched" : "Mark watched"}</button>
        ${nextInSeries ? `<a class="btn quiet" href="#v-${nextInSeries}">Next lecture →</a>` : ""}
      </div>
      ${origBox}
      ${c ? `<div class="box ${v.badge.role === "critique" ? "critique" : GOOD_STATUS.has(c.status) ? "good" : "care"}"><h2>${v.badge.role === "critique" ? "This video pushes back on: " : v.badge.role === "source" ? "What became of it: " : GOOD_STATUS.has(c.status) ? "Holds up: " : "Handle with care: "}${esc(c.name)} ${statusChip(v.badge.id)}</h2><p>${esc(c.note)}</p>${c.sources && c.sources.length ? `<ul class="papers">${c.sources.map(paperLine).join("")}</ul>` : `<p class="faint">${esc(c.source)}.</p>`}<p class="faint" style="margin:0"><a href="#care" style="text-decoration:underline">All replication notes</a></p></div>` : ""}
      ${instBox}${looseBox}
      ${v.nmention ? `<div class="box"><h2>${v.nrec ? "Why people recommend it" : "Where it was mentioned"}</h2>${v.why ? `<p class="why">${esc(v.why)}</p>` : ""}${v.summary ? `<p class="muted">${v.why ? "" : "From the uploader's description: "}${esc(v.summary)}</p>` : ""}${v.quote ? `<p class="quote">“${esc(v.quote)}”</p>` : ""}
        <p class="faint" style="margin:0">${plural(v.nrec, "distinct recommender")} across ${plural(v.communities.length, "community")}; ${plural(v.nmention, "mention")} in total (${srcSummary}), ${v.first === v.last ? v.first : `${v.first}–${v.last}`}.</p></div>` : v.summary ? `<div class="box"><h2>About this lecture</h2><p class="muted">${esc(v.summary)}</p></div>` : ""}
      ${v.clips && v.clips.length ? `<div class="box"><h2>Moments people point to</h2><div class="clips">${v.clips.map(t => { const vo = v.vouches.find(x => x.t === t); return LINKOUT ? `<a class="btn quiet" style="font-size:13px" href="${watchUrl(v, t)}" target="_blank" rel="noopener"><b style="color:var(--amber)">${fmtDur(t)}</b>${vo ? ` <span class="muted">${esc(vo.q.slice(0, 100))}</span>` : ""}</a>` : `<button data-seek="${t}"><b>${fmtDur(t)}</b>${vo ? ` ${esc(vo.q.slice(0, 100))}` : ""}</button>`; }).join("")}</div></div>` : ""}
      ${v.vouches.length ? `<div class="box"><h2>Who vouched</h2><ul class="vlist">${vouchHtml}</ul>${v.nmention > v.vouches.length ? `<p class="faint" style="margin:10px 0 0">Showing ${v.vouches.length} of ${v.nmention} mentions.</p>` : ""}</div>` : ""}
      ${v.cw.length ? `<p class="faint">Content note: ${v.cw.map(x => x.replace(/-/g, " ")).join(", ")}.</p>` : ""}
    </div>
    <aside class="side">
      ${sameSeries ? `<h2>${sameSeries.inst ? `<a href="#s-${sameSeries.id}">${esc(sameSeries.name.length > 48 ? sameSeries.name.slice(0, 46) + "…" : sameSeries.name)}</a>` : "From this series"}</h2>${(posInSeries >= 0 && posInSeries + 1 < sameSeries.vids.length ? sameSeries.vids.slice(posInSeries + 1, posInSeries + 5) : sameSeries.vids.filter(x => x !== id).slice(0, 4)).map(x => byId.get(x)).filter(Boolean).map(x => card(x, { cls: "small", noVouch: true, idx: x.inst ? x.inst.i : undefined })).join("")}${sameSeries.n > 5 ? `<p class="faint" style="margin:4px 0 14px"><a href="#s-${sameSeries.id}" style="text-decoration:underline">All ${sameSeries.n} ${KIND_WORD[sameSeries.kind] || "lecture"}s</a></p>` : ""}` : ""}
      ${rel.length ? `<h2>People who recommended this also recommended</h2>${rel.slice(0, 10).map(x => card(x, { cls: "small", chips: 2 })).join("")}` : ""}
      <h2>More in ${esc(topics.get(v.topics[0]) ? topics.get(v.topics[0]).name : "")}</h2>${sameTopic.map(x => card(x, { cls: "small", chips: 2 })).join("")}
    </aside></div>`;
    document.getElementById("likeBtn").onclick = () => toggleLike(id);
    document.getElementById("laterBtn").onclick = () => toggleLater(id);
    document.getElementById("copyBtn").onclick = () => { const url = LINKOUT ? watchUrl(v, start) : location.href.split("?")[0]; const done = () => toast("Link copied"); try { navigator.clipboard.writeText(url).then(done, () => { window.prompt && prompt("Copy this link", url); }); } catch (e) { toast(url); } };
    main.querySelectorAll("[data-seek]").forEach(b => b.onclick = () => { const t = +b.dataset.seek; if (player) player.seek(t); else location.hash = `#v-${id}?t=${t}`; });
    document.getElementById("doneBtn").onclick = () => { const b = document.getElementById("doneBtn"); markDone(id, !isDone(id)); b.setAttribute("aria-pressed", isDone(id)); b.textContent = isDone(id) ? "✓ Watched" : "Mark watched"; toast(isDone(id) ? "Marked watched" : "Marked unwatched"); };
    if (!LINKOUT) mountPlayer(v, start, () => showUpNext(v, sameSeries, nextInSeries));
    window.scrollTo(0, 0);
  }
  const stanceLabel = k => ({ strong_rec: "strong rec", rec: "recommends", reference: "cites", critical: "critical", joke: "joke", comment: "comment", post: "post", question: "question", answer: "answer" }[k] || k);

  function pageLibrary(kind) {
    const map = { history: ["History", state.history.map(h => byId.get(h.id)).filter(Boolean), "What you've opened here, newest first. Stored only in this browser."], liked: ["Liked", [...state.liked].reverse().map(i => byId.get(i)).filter(Boolean), "Press l on any video to like it."], later: ["Watch later", [...state.later].reverse().map(i => byId.get(i)).filter(Boolean), "Press w on any video to save it for later."] };
    const [title, list, intro] = map[kind];
    setNav(kind); setTitle(title);
    const myCourses = kind === "history" ? PT.series.map(sd => [sd, seriesProgress(sd)]).filter(([sd, sp]) => sp.started).sort((a, b) => b[1].last - a[1].last) : [];
    main.innerHTML = `<h1>${title}</h1><p class="lede">${intro}</p>${myCourses.length ? `<section class="section"><div class="section-head"><div><h2>Your courses</h2><div class="sub">${myCourses.filter(([, sp]) => sp.pct >= 100).length} finished, ${myCourses.filter(([, sp]) => sp.pct < 100).length} in progress.</div></div></div><div class="grid">${myCourses.map(([sd]) => seriesCard(sd)).join("")}</div></section><h2 style="margin:8px 0 10px">Videos</h2>` : ""}${list.length ? `<div class="toolbar"><button class="btn quiet" id="clearBtn">Clear ${title.toLowerCase()}</button></div>${grid(list)}` : `<div class="empty"><h2>Nothing here yet</h2><p>${kind === "history" ? "Open a video and it will show up here." : "Save a video and it will show up here."} <a href="#home" style="text-decoration:underline">Browse the home page</a>.</p></div>`}`;
    const cb = document.getElementById("clearBtn");
    armConfirm(cb, `Clear ${title.toLowerCase()}? Lecture progress is kept; Settings → Export makes a backup first.`, () => { if (kind === "history") { state.history = []; store.set("history", []); } if (kind === "liked") { state.liked.clear(); store.set("liked", []); } if (kind === "later") { state.later.clear(); store.set("later", []); } route(); });
  }
  function pageData() {
    setNav("data"); setTitle("Data");
    const s = PT.stats;
    main.innerHTML = `<h1>The data</h1><div class="prose">
      <p class="lede">Everything behind PsychTube, free to reuse. Give it to your agent and build your own.</p>
      <div class="stats"><div><b>${s.videos.toLocaleString()}</b><span>videos</span></div><div><b>${s.mentions.toLocaleString()}</b><span>mentions (recommendations and citations)</span></div><div><b>${s.communities}</b><span>communities</span></div>${s.inst ? `<div><b>${KINDS.course + KINDS.series}</b><span>courses and lecture series</span></div><div><b>${KINDS.talks}</b><span>seminar and conference collections</span></div><div><b>${s.inst.lectures.toLocaleString()}</b><span>institutional lectures and talks</span></div>` : `<div><b>${PT.series.length}</b><span>lecture series</span></div>`}</div>
      ${ART ? `<p class="muted">This hosted copy can't hand out files. The export (<code>psychtube.json</code> + <code>DATA.md</code>) ships in the project folder next to the site, and the whole pipeline is there to rebuild it.</p>` : `<p><a class="btn primary" href="data/psychtube.json" download>Download psychtube.json</a> <a class="btn" href="data/DATA.md">Read DATA.md</a></p>`}
      <h2>Give it to your agent</h2>
      <p>Download the JSON, open your AI agent in that folder, and tell it what to build. For example:</p>
      <pre>Read DATA.md in this folder. Using psychtube.json, build me a small local web app that shows a weekly
syllabus of three psychology videos per topic area, lets me filter by length and course, and
remembers what I've watched.</pre>
      <h2>Where the vouches come from</h2>
      <ul>${Object.entries(s.sources).map(([k, n]) => `<li><b>${SRC_NAME[k]}</b>: ${n.toLocaleString()} mentions</li>`).join("")}</ul>
      <p>Hacker News mentions come from <a href="https://hackertube.org/data" target="_blank" rel="noopener" style="text-decoration:underline">HackerTube's export</a> (ODC-By, labeled by Claude). Reddit comments come from the Arctic Shift archive of psychology subreddits. Stack Exchange posts come from the Psychology &amp; Neuroscience site via its public API (CC BY-SA). Video titles, channels and lengths come from YouTube and belong to their creators. Topic labels, badges and notes were written by Claude and may contain mistakes.</p>
      ${s.inst && s.inst.courses ? `<p>Course lectures (<code>inst</code> on a video, <code>institutions</code> and the <code>series</code> entries with an <code>inst</code> field) come from ${s.inst.courses} public collections (YouTube playlists, plus a few courses on Panopto and the Internet Archive) published by ${PUBLISHERS} institutions and ${LECTURERS} lecturers' own channels, pulled whole and kept in playlist order: ${KINDS.course} taught courses, ${KINDS.series} lecture series and ${KINDS.talks} collections of seminar, grand-rounds and conference talks. Each lecture carries the institution, the course, its position and the playlist link; lectures no community vouched for have <code>nrec: 0</code>.</p>` : ""}
      <h2>Thumbnails</h2><p>Cards show an automatic frame from the middle of each video (<code>i.ytimg.com/vi/&lt;id&gt;/hq2.jpg</code>) instead of the uploader's thumbnail, so you see what the video looks like, not what the thumbnail designer wants you to feel. Switch to uploader thumbnails in <a href="#prefs" style="text-decoration:underline">settings</a>.</p>
      <p class="faint">Generated ${PT.generated}.</p></div>`;
  }
  function pageAbout() {
    setNav("about"); setTitle("About");
    main.innerHTML = `<h1>About PsychTube</h1><div class="prose">
      <p class="lede">YouTube's recommendations are tuned for the median viewer. Psychology on YouTube is a special kind of bad: confident narrators, "7 signs" lists, findings that collapsed a decade ago. PsychTube flips the question: instead of what the algorithm predicts you'll click, it asks <b>what have psychology people actually told each other to watch?</b></p>
      <h2>How it works</h2>
      <ul>
        <li><b>Mine the vouches.</b> Every comment that links a YouTube video on Hacker News (via HackerTube's export), in ${[...new Set(V.flatMap(v => v.communities))].filter(c => c.startsWith("r/")).length} psychology subreddits (via the Arctic Shift archive), and on Psychology &amp; Neuroscience Stack Exchange.</li>
        <li><b>Keep the psychology.</b> Claude read every candidate (title, channel, description, and the comments that linked it) and kept only videos whose primary subject is psychology, neuroscience, mental health or behavior, then filed each under 1–3 of ${topics.size} topics.</li>
        <li><b>Score by people, not clicks.</b> A video's score is the number of distinct people who recommended it, weighted by how strongly (an enthusiastic HN recommendation counts more than a passing citation; an upvoted answer counts more than a question), with a bonus when several communities agree.</li>
        <li><b>Show the receipts.</b> Each card shows who vouched; each watch page quotes them and links to the original comment.</li>
        <li><b>Keep your place.</b> The player reports where you are, so every lecture resumes where you stopped and every course shows how far you've come — a Continue button that means it, not a 40-tab history. YouTube only remembers one video at a time; here the course is the unit.</li>
        <li><b>Flag the shaky stuff.</b> Videos that present a finding known to have shrunk or failed replication carry a “Handle with care” note with the follow-up research. Videos that push back get a “Pushback” mark.</li>
        ${PT.stats.inst && PT.stats.inst.courses ? `<li><b>Take the universities at their word — video by video.</b> A complete course that a university, one of its lecturers or a scientific institution published is institutional backing of a different kind, so the <a href="#courses" style="text-decoration:underline">Courses</a> hub carries ${PT.stats.inst.lectures.toLocaleString()} lectures and talks from ${PT.stats.inst.courses} collections (${KINDS.course} taught courses, ${KINDS.series} lecture series, ${KINDS.talks} seminar and conference collections) (MIT OpenCourseWare, Yale Courses, Stanford, the IITs via NPTEL, Gresham College, the Royal Institution, professors' own channels…), every lecture in order, whether or not a forum ever linked it. A video is credited to an institution only when it sits on one of the institution's own channels: a TED talk or a CrashCourse clip re-listed in a department's playlist is not the department's lecture, and a playlist that is mostly other channels' videos is a watch list, not a publication. Courses on a lecturer's own channel say so, name the lecturer's affiliation, and say whether an institutional page confirms it; the unconfirmed ones rank with independent talks. Those cards say “Published by” instead of a vouch count, and the lectures the communities <i>also</i> vouched for say both.</li>` : ""}
      </ul>
      <h2>What it deliberately lacks</h2>
      <ul><li>No accounts. History, likes, watch-later and your lecture progress live in your browser (Settings → Export moves them to another device).</li><li>No infinite feed: rows end. Autoplay-next is off unless you turn it on, and then only offers the next lecture of the same course or series.</li><li>No uploader thumbnails by default. You see a frame from the middle of the video.</li></ul>
      <h2>Keyboard</h2><p><kbd class="k">/</kbd> search, <kbd class="k">j</kbd>/<kbd class="k">k</kbd> move, <kbd class="k">Enter</kbd> open, <kbd class="k">l</kbd> like, <kbd class="k">w</kbd> watch later, <kbd class="k">t</kbd> theme, <kbd class="k">Esc</kbd> back.</p>
      <h2>Credits</h2><p>Built in an afternoon with Claude, in the spirit of Andrej Karpathy's <a href="https://hackertube.org" target="_blank" rel="noopener" style="text-decoration:underline">HackerTube</a>, whose open data seeded this. Comments belong to their authors; videos to their creators. Not affiliated with YouTube, Reddit, Hacker News or Stack Exchange.</p></div>`;
  }
  function pageSettings() {
    setNav("settings"); setTitle("Settings");
    const s = state.settings;
    const seg = (key, items) => `<div class="seg">${items.map(([val, label]) => `<button data-set="${key}" data-val="${val}" aria-pressed="${s[key] === val}">${label}</button>`).join("")}</div>`;
    main.innerHTML = `<h1>Settings</h1>
      <div class="setting"><div><b>Theme</b><p>Dark is the default; system follows your OS.</p></div>${seg("theme", [["dark", "Dark"], ["light", "Light"], ["system", "System"]])}</div>
      ${LINKOUT ? "" : `<div class="setting"><div><b>Thumbnails</b><p>A frame from the middle of the video, or the uploader's designed thumbnail.</p></div>${seg("thumbs", [["mid", "Middle frame"], ["uploader", "Uploader's"]])}</div>
      <div class="setting"><div><b>Autoplay when opening a video</b><p>The player starts immediately on the watch page. Never autoplays a next video.</p></div>${seg("autoplay", [[true, "On"], [false, "Off"]])}</div>`}
      <div class="setting"><div><b>Hide “handle with care” videos</b><p>Removes videos built on contested findings from every list except the Replication notes page.</p></div>${seg("hideCare", [[false, "Show"], [true, "Hide"]])}</div>
      <div class="setting"><div><b>Single-key shortcuts</b><p>j/k move between cards, l likes, w saves for later, t switches the theme. Turn them off if a screen reader or your own keys conflict; / for search and Esc still work.</p></div>${seg("keys", [[true, "On"], [false, "Off"]])}</div>
      <div class="setting"><div><b>Hide videos with content notes</b><p>Videos substantially about suicide, self-harm, eating disorders, abuse or substance use stay out of browsing rows. Search and direct links still work.</p></div>${seg("hideCW", [[true, "Hide"], [false, "Show"]])}</div>
      ${LINKOUT ? "" : `<div class="setting"><div><b>When a lecture ends</b><p>Inside a course, the next lecture is one click away. "Play it" starts it after an 8-second countdown you can cancel. Never applies outside a course.</p></div>${seg("autoNext", [["ask", "Show the next one"], ["auto", "Play it"], ["off", "Do nothing"]])}</div>`}
      <div class="setting"><div><b>Your data</b><p>History, likes, watch-later and lecture progress are stored only in this browser. Export them to move to another browser or device.</p></div><div style="display:flex;gap:8px;flex-wrap:wrap">${ART ? "" : `<button class="btn quiet" id="exportBtn">Export</button><label class="btn quiet" style="cursor:pointer">Import<input type="file" id="importFile" accept="application/json" hidden></label>`}<button class="btn quiet" id="wipeBtn">Clear everything</button></div></div>`;
    const ex = document.getElementById("exportBtn");
    if (ex) ex.onclick = () => { const blob = new Blob([JSON.stringify({ psychtube: 1, exported: new Date().toISOString(), history: state.history, liked: [...state.liked], later: [...state.later], progress: state.progress, settings: state.settings }, null, 1)], { type: "application/json" }); const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = `psychtube-data-${new Date().toISOString().slice(0, 10)}.json`; document.body.appendChild(a); a.click(); a.remove(); };
    const imp = document.getElementById("importFile");
    if (imp) imp.onchange = () => { const f = imp.files[0]; if (!f) return; f.text().then(txt => { const d = JSON.parse(txt); if (!d || !d.psychtube) throw new Error("not a PsychTube export"); const ids = new Set(V.map(v => v.id)); if (Array.isArray(d.history)) state.history = [...d.history.filter(h => ids.has(h.id)), ...state.history.filter(h => !d.history.some(x => x.id === h.id))].slice(0, 500); if (Array.isArray(d.liked)) d.liked.forEach(x => ids.has(x) && state.liked.add(x)); if (Array.isArray(d.later)) d.later.forEach(x => ids.has(x) && state.later.add(x)); if (d.progress && typeof d.progress === "object") for (const [k, p] of Object.entries(d.progress)) { if (ids.has(k) && p && typeof p.t === "number") { const cur = state.progress[k]; if (!cur || (p.ts || 0) >= (cur.ts || 0) || p.done) state.progress[k] = { t: +p.t || 0, d: +p.d || 0, done: !!p.done, ts: +p.ts || Date.now() }; } } store.set("history", state.history); store.set("liked", [...state.liked]); store.set("later", [...state.later]); store.set("progress", state.progress); if (d.settings && typeof d.settings === "object") { for (const k of ["theme", "thumbs", "hideCare", "hideCW", "autoplay", "autoNext", "background", "keys"]) if (k in d.settings) s[k] = d.settings[k]; saveSettings(); applyTheme(); } toast("Imported"); pageSettings(); }).catch(e => toast("Couldn't import: " + e.message)); };
    main.querySelectorAll("[data-set]").forEach(b => b.onclick = () => { const val = b.dataset.val === "true" ? true : b.dataset.val === "false" ? false : b.dataset.val; s[b.dataset.set] = val; saveSettings(); applyTheme(); pageSettings(); });
    armConfirm(document.getElementById("wipeBtn"), "Clear history, likes, watch later and every lecture's progress from this browser? This can't be undone.", () => { ["history", "liked", "later"].forEach(k => store.set(k, [])); store.set("progress", {}); state.history = []; state.liked.clear(); state.later.clear(); state.progress = {}; toast("Cleared"); pageSettings(); });
  }
  function notFound() { setTitle("Not found"); main.innerHTML = `<div class="empty"><h2>Not here</h2><p>That video or page isn't in the catalog. <a href="#home" style="text-decoration:underline">Back to the home page</a>.</p></div>`; }

  // ------------------------------------------------------------ actions
  function toast(msg) { const t = document.getElementById("toast"); t.textContent = msg; t.classList.add("on"); clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.remove("on"), 1600); }
  function toggleLike(id) { if (state.liked.has(id)) { state.liked.delete(id); toast("Removed from liked"); } else { state.liked.add(id); toast("Liked"); } store.set("liked", [...state.liked]); const b = document.getElementById("likeBtn"); if (b) { b.setAttribute("aria-pressed", state.liked.has(id)); b.textContent = `♥ ${state.liked.has(id) ? "Liked" : "Like"}`; } }
  function toggleLater(id) { if (state.later.has(id)) { state.later.delete(id); toast("Removed from watch later"); } else { state.later.add(id); toast("Saved for later"); } store.set("later", [...state.later]); const b = document.getElementById("laterBtn"); if (b) { b.setAttribute("aria-pressed", state.later.has(id)); b.textContent = state.later.has(id) ? "In watch later" : "Watch later"; } }

  // ------------------------------------------------------------ router
  let current = { page: "", id: "" };
  function route() {
    unmountPlayer(); clearInterval(upNextTimer);
    // routes are plain hash names: #home, #v-<id>, #t-<topic>, #a-<area>, #s-<series>, #q-<query>, #topics, #prefs ...
    // in-page filters ride along after "?" (e.g. #t-memory?sort=newest); legacy "#/v/<id>" links still work.
    const raw = location.hash.replace(/^#/, "");
    const dec = s => { try { return decodeURIComponent(s); } catch (e) { return s; } };   // a malformed %-escape must not kill the router
    const qi = raw.indexOf("?");                                                         // split before decoding, so an encoded "?" stays in a search
    let path = dec(qi < 0 ? raw : raw.slice(0, qi)) || "home";
    const params = Object.fromEntries(new URLSearchParams(qi < 0 ? "" : raw.slice(qi + 1)));
    if (path.startsWith("/")) { path = path.slice(1).replace(/^(v|t|a|s)\//, "$1-").replace(/^settings/, "prefs") || "home"; if (path === "search" && params.q) path = "q-" + params.q; }
    const m = /^(v|t|a|s|q|shelf)-(.+)$/.exec(path);
    const p0 = m ? m[1] : path;
    const arg = m ? m[2] : "";
    const pageChanged = !(current.page === p0 && current.id === arg) && !first;   // a filter change on the same page keeps the viewer's focus
    current = { page: p0, id: arg };
    if (p0 !== "q") document.getElementById("q").value = "";
    if (p0 === "home" || p0 === "" || p0 === "main") pageHome();
    else if (p0 === "v") pageWatch(arg, params);
    else if (p0 === "t") pageTopic(arg, params);
    else if (p0 === "a") pageArea(arg, params);
    else if (p0 === "topics") pageTopics();
    else if (p0 === "courses") pageCourses(params);
    else if (p0 === "s") pageSeries(arg);
    else if (p0 === "clips") pageClips();
    else if (p0 === "care") pageCare(params);
    else if (p0 === "shelf") pageShelf(arg);
    else if (p0 === "pathways") pagePathways(params);
    else if (p0 === "longs") pageSimple("longs", "Over an hour", "Full lectures, long interviews and documentaries: everything over an hour, ordered by who published it first.", V.filter(v => visible(v) && v.len >= 3600), params, "longs");
    else if (p0 === "canon") pageSimple("", "The canon", "The most vouched-for psychology videos across every community, by distinct recommenders.", V.filter(v => visible(v) && v.nrec > 0).sort((a, b) => (b.cscore != null ? b.cscore : b.score) - (a.cscore != null ? a.cscore : a.score)), params, "canon");
    else if (p0 === "history" || p0 === "liked" || p0 === "later") pageLibrary(p0);
    else if (p0 === "q") pageSearch({ q: arg });
    else if (p0 === "data") pageData();
    else if (p0 === "about") pageAbout();
    else if (p0 === "prefs") pageSettings();
    else notFound();
    if (p0 !== "v") window.scrollTo(0, 0);
    if (pageChanged) {
      // focus moves to the new page's heading, so screen readers announce it and keyboard users start at the top
      const h = main.querySelector("h1"); const target = h || main;
      if (h && !h.hasAttribute("tabindex")) h.setAttribute("tabindex", "-1");
      try { target.focus({ preventScroll: true }); } catch (e) { /* ignore */ }
    }
    first = false;
  }
  let first = true;
  let depth = (history.state && history.state.ptDepth) || 0;
  try { history.replaceState({ ...(history.state || {}), ptDepth: depth }, ""); } catch (e) { /* sandboxed */ }
  window.addEventListener("hashchange", () => {
    if (history.state && typeof history.state.ptDepth === "number") depth = history.state.ptDepth;
    else { depth += 1; try { history.replaceState({ ptDepth: depth }, ""); } catch (e) { /* sandboxed */ } }
    route();
  });

  // ------------------------------------------------------------ search box
  const q = document.getElementById("q");
  document.getElementById("searchForm").addEventListener("submit", e => { e.preventDefault(); const val = q.value.trim(); if (val) location.hash = "#q-" + encodeURIComponent(val); });
  let typing;
  q.addEventListener("input", () => { clearTimeout(typing); typing = setTimeout(() => { const val = q.value.trim(); if (val.length >= 2) { history.replaceState(history.state, "", "#q-" + encodeURIComponent(val)); pageSearch({ q: val }); q.focus(); } }, 220); });

  // ------------------------------------------------------------ keyboard
  document.getElementById("themeBtn").onclick = () => { state.settings.theme = effectiveTheme() === "dark" ? "light" : "dark"; saveSettings(); applyTheme(); };
  document.getElementById("helpBtn").onclick = () => document.getElementById("helpDialog").showModal();
  document.addEventListener("keydown", e => {
    const inField = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName) || document.activeElement.isContentEditable;
    if (e.key === "Escape") { if (inField) { document.activeElement.blur(); return; } const d = document.getElementById("helpDialog"); if (d.open) { d.close(); return; } if (current.page && depth > 0) history.back(); return; }
    if (inField || e.metaKey || e.ctrlKey || e.altKey) return;
    if (/^(VIDEO|AUDIO|IFRAME)$/.test(document.activeElement.tagName)) return;   // the media element owns its keys
    if (e.key === "/") { e.preventDefault(); q.focus(); q.select(); return; }
    if (e.key === "?") { document.getElementById("helpDialog").showModal(); return; }
    if (state.settings.keys === false && /^[a-z]$/i.test(e.key)) return;        // single-letter shortcuts are off (Settings): WCAG 2.1.4
    if (e.key === "t") { document.getElementById("themeBtn").click(); return; }
    const cards = [...main.querySelectorAll("a.card[data-id], .lectures a.lt")];
    const i = cards.indexOf(document.activeElement);
    if ((e.key === "ArrowRight" || e.key === "ArrowLeft") && i < 0) return;      // arrows move between cards only when a card has focus
    if (e.key === "j" || e.key === "ArrowRight") { e.preventDefault(); const n = cards[Math.min(cards.length - 1, i + 1)]; if (n) { n.focus(); n.scrollIntoView({ block: "nearest", inline: "nearest" }); } return; }
    if (e.key === "k" || e.key === "ArrowLeft") { e.preventDefault(); const n = cards[Math.max(0, i - 1)]; if (n) { n.focus(); n.scrollIntoView({ block: "nearest", inline: "nearest" }); } return; }
    const focusedId = document.activeElement && document.activeElement.dataset ? document.activeElement.dataset.id : null;
    const target = current.page === "v" ? current.id : focusedId;
    if (e.key === "l" && target) { toggleLike(target); return; }
    if (e.key === "w" && target) { toggleLater(target); return; }
  });

  document.querySelector(".skip").addEventListener("click", e => { e.preventDefault(); main.focus(); main.scrollIntoView(); });
  route();
})();
