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
  }
  const byId = new Map(V.map(v => [v.id, v]));
  const topics = new Map();
  const areaOf = new Map();
  const areas = PT.areas;
  for (const a of areas) for (const t of a.topics) { topics.set(t.id, t); areaOf.set(t.id, a); }
  const series = new Map(PT.series.map(s => [s.id, s]));
  const maxScore = Math.max(...V.map(v => v.score));
  const SRC_NAME = { hn: "Hacker News", reddit: "Reddit", se: "Psych SE" };

  // ------------------------------------------------------------ local state
  const store = {
    get(k, d) { try { const v = localStorage.getItem("pt:" + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem("pt:" + k, JSON.stringify(v)); } catch (e) { /* private mode etc. */ } },
  };
  const state = {
    history: store.get("history", []),      // [{id, ts}] newest first
    liked: new Set(store.get("liked", [])),
    later: new Set(store.get("later", [])),
    settings: Object.assign({ theme: window.PT_ARTIFACT ? "system" : "dark", thumbs: "mid", hideCare: false, hideCW: true, autoplay: true }, store.get("settings", {})),
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
  const SITE_URL = "https://contofalskyr.github.io/psychtube/";   // the live copy, where players embed in the page
  // videos are YouTube unless v.p names another provider (Panopto for courses universities host themselves)
  const PROVIDER_NAME = { youtube: "YouTube", panopto: "Panopto" };
  const providerOf = v => PROVIDER_NAME[(v && v.p) || "youtube"] || v.p;
  const vidOf = x => (typeof x === "string" ? byId.get(x) : x);
  const thumbUrl = (x, mode) => {
    const v = vidOf(x); const id = v ? v.id : x;
    if (ART) return THUMBS[id] || "";
    if (v && v.p === "panopto") return `https://${v.host}/Panopto/Services/FrameGrabber.svc/FrameRedirect?objectId=${id}&mode=Delivery&random=1`;
    return `https://i.ytimg.com/vi/${id}/${(mode || state.settings.thumbs) === "mid" ? "hq2" : "hqdefault"}.jpg`;
  };
  const watchUrl = (x, t) => {
    const v = vidOf(x); const id = v ? v.id : x;
    if (v && v.p === "panopto") return `https://${v.host}/Panopto/Pages/Viewer.aspx?id=${id}${t ? "&start=" + t : ""}`;
    return `https://www.youtube.com/watch?v=${id}${t ? "&t=" + t + "s" : ""}`;
  };
  const embedUrl = (v, start, autoplay) => v.p === "panopto"
    ? `https://${v.host}/Panopto/Pages/Embed.aspx?id=${v.id}&autoplay=${autoplay ? "true" : "false"}&offerviewer=true&showtitle=false&showbrand=false&captions=false&interactivity=all${start ? "&start=" + start : ""}`
    : `https://www.youtube-nocookie.com/embed/${v.id}?rel=0&modestbranding=1${start ? "&start=" + start : ""}${autoplay ? "&autoplay=1" : ""}`;
  const dayseed = () => { const d = new Date(); return d.getFullYear() * 400 + d.getMonth() * 31 + d.getDate(); };
  const rng = seed => () => { seed = (seed * 1664525 + 1013904223) % 4294967296; return seed / 4294967296; };
  const isWatched = id => state.history.some(h => h.id === id);
  const visible = v => (!state.settings.hideCare || !v.badge || v.badge.role === "critique") && (!state.settings.hideCW || !v.cw.length);

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
  const instShort = name => { const i = (PT.institutions || []).find(x => x.name === name); return i ? i.short : name; };
  const instChip = v => v.inst ? `<span class="chip inst" title="Published by ${esc(v.inst.n)}">${esc(instShort(v.inst.n))}</span>` : "";
  function vouchLine(v, max) {
    const n = v.nrec || v.nmention;
    if (!n && v.inst) return `<div class="vouch"><span class="pub">Published by</span> ${instChip(v)}<span class="faint">lecture ${v.inst.i} of ${v.inst.of}</span></div>`;
    return `<div class="vouch"><span class="n">${n}</span>${n === 1 ? "vouch" : "vouches"} ${communityChips(v, max)}${instChip(v)}</div>`;
  }
  function tagFor(v, idx) {
    if (v.badge && v.badge.role !== "critique") return `<span class="tag" title="${esc(PT.contested[v.badge.id].name)}">Handle with care</span>`;
    if (v.badge && v.badge.role === "critique") return `<span class="tag critique">Debunk</span>`;
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
  function thumb(v, idx) {
    return `<div class="thumb">${placeholder(v)}${img(v.id)}${tagFor(v, idx)}${v.len ? `<span class="pill">${fmtDur(v.len)}</span>` : ""}</div>`;
  }
  window.__ptPoster = (img, id, failed) => {
    // hq720 -> hq2 (frame from the middle) -> hqdefault; a 120px-wide "image" is YouTube's placeholder, not a frame
    const steps = ["hq720", "hq2", "hqdefault"]; const i = +img.dataset.step;
    if (!failed && img.naturalWidth > 200) return;
    if (i >= steps.length - 1) { if (failed) img.style.visibility = "hidden"; return; }
    img.dataset.step = String(i + 1); img.src = `https://i.ytimg.com/vi/${id}/${steps[i + 1]}.jpg`;
  };
  window.__ptImgErr = img => {
    if (ART || !img.src || /FrameGrabber/.test(img.src)) { img.style.visibility = "hidden"; return; }
    if (img.dataset.fb === "1") { img.dataset.fb = "2"; img.src = img.src.replace(/\/(hq2|hqdefault)\.jpg/, "/hqdefault.jpg"); }
    else if (img.dataset.fb === "2") { img.dataset.fb = "3"; img.src = img.src.replace("hqdefault", "mqdefault"); }
    else { img.style.visibility = "hidden"; }
  };
  const card = (v, opts = {}) => `<a class="card ${opts.cls || ""}" href="#v-${v.id}" data-id="${v.id}">${thumb(v, opts.idx)}<div class="body"><div class="title">${esc(v.title)}</div><div class="ch">${esc(v.ch || "")}</div>${opts.noVouch ? "" : vouchLine(v, opts.chips)}${opts.desc ? `<div class="desc">${esc(v.why || v.summary)}</div>` : ""}</div></a>`;
  const grid = (list, opts) => list.length ? `<div class="grid">${list.map(v => card(v, opts)).join("")}</div>` : "";
  const rowOf = (list, opts) => `<div class="row">${list.map(v => card(v, opts)).join("")}</div>`;
  const section = (title, body, more, sub) => body ? `<section class="section"><div class="section-head"><div><h2>${title}</h2>${sub ? `<div class="sub">${sub}</div>` : ""}</div>${more ? `<a class="more" href="${more}">See all</a>` : ""}</div>${body}</section>` : "";

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
      const tops = [...topics.keys()].sort(() => r() - 0.5);
      for (const t of tops) {
        const cands = V.filter(v => visible(v) && v.topics[0] === t && !used.has(v.id) && !(v.badge && v.badge.role !== "critique") && (v.nrec >= 2 || v.score >= 2.5)).slice(0, 3);
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
  const index = V.map(v => {
    const sd = v.series ? series.get(v.series) : null;
    return {
      v,
      title: norm(v.title), ch: norm([v.ch, v.inst ? v.inst.n : "", sd && sd.inst ? sd.name + " " + (sd.lecturer || "") + " " + (sd.short || "") : ""].join(" ")),
      topicText: norm(v.topics.map(t => topics.get(t) ? topics.get(t).name + " " + topics.get(t).desc : t).join(" ")),
      text: norm([v.why, v.summary, v.quote, (v.kw || []).join(" "), v.communities.join(" "), ...v.vouches.map(x => x.q)].join(" ")),
    };
  });
  function search(q, limit) {
    const terms = norm(q).split(/\s+/).filter(Boolean);
    if (!terms.length) return [];
    const res = [];
    for (const e of index) {
      let s = 0, ok = true;
      for (const t of terms) {
        let ts = 0;
        if (e.title.includes(t)) ts += 6 + (e.title.startsWith(t) ? 2 : 0);
        if (e.ch.includes(t)) ts += 4;
        if (e.topicText.includes(t)) ts += 2;
        if (e.text.includes(t)) ts += 1;
        if (!ts) { ok = false; break; }
        s += ts;
      }
      if (ok) res.push([s + Math.log1p(e.v.score), e.v]);
    }
    return res.sort((a, b) => b[0] - a[0]).slice(0, limit || 200).map(x => x[1]);
  }

  // ------------------------------------------------------------ pages
  const main = document.getElementById("main");
  function setNav(id) { document.querySelectorAll(".rail a").forEach(a => { if (a.dataset.nav === id) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current"); }); }
  function setTitle(t) { if (t) { const ta = document.createElement("textarea"); ta.innerHTML = t; t = ta.value; } document.title = t ? `${t} — PsychTube` : "PsychTube"; }

  function pageHome() {
    setNav("home"); setTitle("");
    const s = PT.stats;
    const fy = forYou(12);
    const canon = V.filter(visible).slice(0, 12);
    const recent = V.filter(v => visible(v) && v.last >= 2024).sort((a, b) => (b.last - a.last) || (b.score - a.score)).slice(0, 12);
    const care = V.filter(v => v.badge && v.badge.role !== "critique" && !(state.settings.hideCW && v.cw.length)).slice(0, 12);
    const longs = V.filter(v => visible(v) && v.len >= 3600).slice(0, 12);
    const seriesRow = PT.series.slice(0, 8).map(sid => { const first = byId.get(sid.vids[0]); return { ...first, title: `${sid.name}: ${sid.n} lectures`, id: first.id, _series: sid }; });
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
    const courseRow = PT.series.filter(sd => sd.inst).slice(0, 10);
    main.innerHTML = `
      <div class="masthead">
        <h1>The psychology videos that psychology people keep telling each other to watch${inst.courses ? " — and the courses universities put online" : ""}.</h1>
        <p class="lede"><b>${(s.vouched || s.videos).toLocaleString()}</b> videos vouched for in <b>${s.mentions.toLocaleString()}</b> comments across ${whereText}${inst.courses ? `, plus <b>${inst.lectures.toLocaleString()}</b> lectures from <b>${inst.courses}</b> complete courses published by ${inst.institutions} universities and scientific institutions` : ""}. No algorithm, no accounts, no autoplay rabbit hole. Every card shows who vouched, or who published.${hidden ? ` <span class="faint">${hidden} with content notes are hidden (<a href="#prefs" style="text-decoration:underline">settings</a>).</span>` : ""}</p>
      </div>
      ${section(state.history.length ? "For you" : "Start here", rowOf(fy), null, state.history.length ? "Based on what you've watched here. Nothing leaves your browser." : "A fresh mix every day, one video per topic.")}
      ${courseRow.length ? section("Courses", `<div class="row">${courseRow.map(sd => seriesCard(sd)).join("")}</div>`, "#courses", `Complete courses, every lecture in order, published by the universities themselves. ${inst.courses} courses from ${inst.institutions} institutions.`) : ""}
      ${section("The canon", rowOf(canon), "#canon", "The most vouched-for videos across all communities.")}
      ${!courseRow.length && PT.series.length ? section("Courses & series", `<div class="row">${PT.series.slice(0, 8).map(sd => seriesCard(sd)).join("")}</div>`, "#courses", "Full lecture series people recommend whole.") : ""}
      ${section("Recently recommended", rowOf(recent), null, "Vouched for in 2024 or later.")}
      ${areaRows}
      ${care.length ? section("Handle with care", rowOf(care), "#care", "Popular videos built on findings that later shrank, failed to replicate or were overstated. Watch, then read the note.") : ""}
      ${section("Long watches", rowOf(longs), "#longs", "Everything over an hour.")}
    `;
  }
  const KIND_WORD = { course: "lecture", series: "lecture", talks: "talk" };
  function seriesCard(sd) {
    const first = byId.get(sd.vids[0]);
    const done = sd.vids.filter(id => isWatched(id)).length;
    const unit = KIND_WORD[sd.kind] || "lecture";
    const who = sd.inst ? [sd.lecturer, sd.year].filter(Boolean).join(", ") || sd.ch : first.ch;
    const ph = sd.inst ? `<div class="ph lec" style="--h:${hueOf(sd.id)}" aria-hidden="true"><b>${sd.n}</b><span>${esc(sd.short || sd.inst)}</span></div>` : "";
    const tail = done ? `<span class="n">${done}/${sd.n}</span> watched` : sd.inst ? `<span class="chip inst">${esc(sd.short || sd.inst)}</span>${sd.vouched ? `<span class="faint">${sd.vouched} vouched</span>` : ""}` : sd.topics.map(t => `<span class="chip">${esc(topics.get(t) ? topics.get(t).name : t)}</span>`).join("");
    return `<a class="card course" href="#s-${sd.id}" data-id="${first.id}"><div class="thumb">${ph}${img(first.id)}<span class="tag series">${sd.n} ${unit}s${sd.hours >= 1 ? ` · ${Math.round(sd.hours)} h` : ""}</span></div><div class="body"><div class="title">${esc(sd.name)}</div><div class="ch">${esc(who || "")}</div><div class="vouch">${tail}</div></div></a>`;
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
    if (src === "vouched") list = list.filter(v => v.nrec > 0);
    if (src === "course") list = list.filter(v => v.inst);
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
    const seg = (k, cur, items) => `<div class="seg" role="group">${items.map(([val, label]) => `<a role="button" href="${link(k, val)}" aria-pressed="${cur === val}" class="segbtn">${label}</a>`).join("")}</div>`;
    main.innerHTML = `
      <h1>${opts.title}</h1>
      ${opts.intro ? `<p class="lede">${opts.intro}</p>` : ""}
      ${opts.extra || ""}
      <div class="toolbar">
        ${seg("sort", sort, [["vouched", "Most vouched"], ["recent", "Recently recommended"], ["newest", "Newest upload"], ["shortest", "Shortest"], ["longest", "Longest"]])}
        ${opts.list.some(v => v.inst) && opts.list.some(v => v.nrec) ? seg("src", src, [["any", "All"], ["vouched", "Community-vouched"], ["course", "Course lectures"]]) : ""}
        ${seg("dur", dur, [["any", "Any length"], ["short", "Under 20 min"], ["medium", "20–60 min"], ["long", "Over 1 h"]])}
        ${types.length > 1 ? `<select class="btn" id="typeSel" aria-label="Type"><option value="any">Any type</option>${types.map(t => `<option value="${t}" ${t === type ? "selected" : ""}>${t}</option>`).join("")}</select>` : ""}
        <span class="faint">${plural(list.length, "video")}</span>
      </div>
      ${list.length ? grid(list) : `<div class="empty"><h2>Nothing matches these filters</h2><p>Try another length or type.</p></div>`}`;
    const sel = document.getElementById("typeSel");
    if (sel) sel.onchange = () => { location.hash = link("type", sel.value); };
  }

  function pageTopic(id, params) {
    const t = topics.get(id); if (!t) return notFound();
    const a = areaOf.get(id);
    const list = V.filter(v => v.topics.includes(id) && visible(v)).sort((x, y) => (x.topics[0] === id ? 0 : 1) - (y.topics[0] === id ? 0 : 1) || y.score - x.score);
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
    const kind = p.kind || "any", level = p.level || "any";
    const instSeries = PT.series.filter(sd => sd.inst && (kind === "any" || sd.kind === kind) && (level === "any" || sd.level === level));
    const vouchedSeries = PT.series.filter(sd => !sd.inst);
    const byInst = new Map();
    for (const sd of instSeries) { const a = byInst.get(sd.inst) || []; a.push(sd); byInst.set(sd.inst, a); }
    const rank = list => list.reduce((a, sd) => a + sd.pop, 0) + 0.01 * list.reduce((a, sd) => a + sd.n, 0);
    const groups = [...byInst.entries()].sort((a, b) => rank(b[1]) - rank(a[1]));
    const s = PT.stats.inst || { courses: 0, lectures: 0, institutions: 0, also_vouched: 0 };
    const link = (k, val) => `#courses?${new URLSearchParams({ ...p, [k]: val }).toString()}`;
    const seg = (k, cur, items) => `<div class="seg" role="group">${items.map(([val, label]) => `<a role="button" href="${link(k, val)}" aria-pressed="${cur === val}" class="segbtn">${label}</a>`).join("")}</div>`;
    const lectures = instSeries.reduce((a, sd) => a + sd.n, 0);
    main.innerHTML = `<h1>Courses</h1>
      <p class="lede">${s.courses ? `<b>${s.lectures.toLocaleString()}</b> lectures in <b>${s.courses}</b> complete courses and lecture series, published by <b>${s.institutions}</b> universities and scientific institutions. Every lecture is here, in order, because the institution put it online — institutional backing instead of a vouch count. Where a community also vouched for a lecture, the card says so (${s.also_vouched} lectures so far). Your progress is remembered in this browser.` : "Lecture series where several lectures were recommended, grouped by channel. Your progress is remembered in this browser."}</p>
      ${s.courses ? `<div class="toolbar">${seg("kind", kind, [["any", "All"], ["course", "Taught courses"], ["series", "Lecture series"], ["talks", "Talk collections"]])}${seg("level", level, [["any", "Any level"], ["intro", "Intro"], ["advanced", "Advanced"], ["public", "Public lectures"]])}<span class="faint">${plural(instSeries.length, "course")}, ${plural(lectures, "lecture")}</span></div>` : ""}
      ${groups.map(([name, list]) => `<section class="section"><div class="section-head"><div><h2>${esc(name)}</h2><div class="sub">${plural(list.length, "course")} · ${plural(list.reduce((a, sd) => a + sd.n, 0), "lecture")} · ${Math.round(list.reduce((a, sd) => a + sd.hours, 0))} hours${list[0].ch ? ` · published on YouTube by ${esc([...new Set(list.map(sd => sd.ch))].slice(0, 3).join(", "))}` : ""}</div></div></div><div class="grid">${list.map(sd => seriesCard(sd)).join("")}</div></section>`).join("")}
      ${!groups.length && s.courses ? `<div class="empty"><h2>Nothing matches these filters</h2></div>` : ""}
      ${vouchedSeries.length ? `<section class="section"><div class="section-head"><div><h2>Series people recommend piece by piece</h2><div class="sub">Channels where several lectures were vouched for individually; not complete courses.</div></div></div><div class="grid">${vouchedSeries.map(sd => seriesCard(sd)).join("")}</div></section>` : ""}`;
  }
  function pageSeries(id) {
    const sd = series.get(id); if (!sd) return notFound();
    setNav("courses"); setTitle(sd.name);
    const vids = sd.vids.map(i => byId.get(i)).filter(Boolean);
    const next = vids.find(v => !isWatched(v.id)) || vids[0];
    const watched = vids.filter(v => isWatched(v.id)).length;
    const unit = KIND_WORD[sd.kind] || "lecture";
    const meta = sd.inst ? [sd.lecturer, sd.year, sd.level === "intro" ? "introductory" : sd.level === "advanced" ? "advanced" : sd.level === "public" ? "public lectures" : "", `${plural(vids.length, unit)}${sd.total > vids.length ? ` of ${sd.total}` : ""}`, sd.hours >= 1 ? `${Math.round(sd.hours)} hours` : ""].filter(Boolean) : [];
    main.innerHTML = `<div class="course-head">
      ${sd.inst ? `<div class="eyebrow"><span class="chip inst">${esc(sd.inst)}</span> ${sd.kind === "talks" ? "talk collection" : sd.kind === "series" ? "lecture series" : "complete course"}</div>` : ""}
      <h1>${esc(sd.name)}</h1>
      ${sd.inst ? `<p class="lede">${sd.note ? esc(sd.note) + " " : ""}<span class="muted">${meta.map(esc).join(" · ")}.</span>${sd.vouched ? ` <span class="muted">${sd.vouched === vids.length ? "Every" : sd.vouched} ${sd.vouched === 1 ? unit + " was" : unit + "s were"} also vouched for by the communities.</span>` : ""}${watched ? ` You've watched ${watched}.` : ""}</p>` : `<p class="lede">${plural(vids.length, "lecture")} people recommended from this series. ${watched ? `You've watched ${watched}.` : ""}</p>`}
      <div class="toolbar"><a class="btn primary" href="#v-${next.id}">${isWatched(vids[0].id) && next !== vids[0] ? "Continue" : "Start"}: ${esc(next.title.slice(0, 60))}</a>${sd.url ? `<a class="btn quiet" href="${esc(sd.url)}" target="_blank" rel="noopener">${sd.provider === "panopto" ? "Course on Panopto" : "Playlist on YouTube"} ↗</a>` : ""}${sd.chid || next.chid ? `<a class="btn quiet" href="https://www.youtube.com/channel/${esc(sd.chid || next.chid)}" target="_blank" rel="noopener">${esc(sd.ch || next.ch || "Channel")} ↗</a>` : ""}${sd.topics.map(t => `<a class="chip" href="#t-${t}">${esc(topics.get(t) ? topics.get(t).name : t)}</a>`).join("")}</div></div>
      <ol class="lectures">${vids.map((v, i) => `<li><span class="num">${sd.inst ? v.inst.i : i + 1}</span><a class="thumb" href="#v-${v.id}" aria-label="${esc(v.title)}">${sd.inst && !thumbUrl(v.id) ? `<div class="ph lec" style="--h:${hueOf(sd.id)}" aria-hidden="true"><b>${v.inst.i}</b></div>` : ""}${img(v.id)}${v.len ? `<span class="pill">${fmtDur(v.len)}</span>` : ""}</a><div><a class="lt" href="#v-${v.id}">${esc(v.title)}</a>${v.why || (v.summary && !sd.inst) ? `<div class="muted" style="font-size:13.5px">${esc(v.why || v.summary)}</div>` : ""}${v.nrec ? vouchLine(v) : sd.inst ? `<div class="vouch"><span class="faint">${v.len ? fmtLen(v.len) : ""}${v.topics[0] && v.topics[0] !== sd.topics[0] ? ` · ${esc(topics.get(v.topics[0]).name)}` : ""}</span></div>` : ""}${isWatched(v.id) ? `<div class="watched">Watched</div>` : ""}</div></li>`).join("")}</ol>`;
  }
  function pageClips() {
    setNav("clips"); setTitle("Clips");
    const list = V.filter(v => visible(v) && v.clips && v.clips.length);
    main.innerHTML = `<h1>Clips</h1><p class="lede">Moments people linked to directly, with a timestamp. Psychology people point at the specific minute.</p>
      ${list.map(v => `<div class="card row-item"><a class="thumb" href="#v-${v.id}?t=${v.clips[0]}" aria-label="${esc(v.title)}">${thumb(v).replace('<div class="thumb">', "").replace(/<\/div>$/, "")}</a><div><a class="title" href="#v-${v.id}">${esc(v.title)}</a><div class="ch">${esc(v.ch)}</div><div class="clips" style="margin-top:8px">${v.clips.map(t => { const vo = v.vouches.find(x => x.t === t); return `<a class="btn quiet" style="font-size:13px" href="#v-${v.id}?t=${t}"><b style="color:var(--amber)">${fmtDur(t)}</b>${vo ? ` <span class="muted">${esc(vo.q.slice(0, 90))}${vo.q.length > 90 ? "…" : ""}</span>` : ""}</a>`; }).join("")}</div></div></div>`).join("") || `<div class="empty"><h2>No clips yet</h2></div>`}`;
  }
  function pageCare() {
    setNav("care"); setTitle("Handle with care");
    const groups = new Map();
    for (const v of V) if (v.badge) { const g = groups.get(v.badge.id) || { promotes: [], critique: [] }; g[v.badge.role === "critique" ? "critique" : "promotes"].push(v); groups.set(v.badge.id, g); }
    const order = [...groups.keys()].sort((a, b) => (groups.get(b).promotes.length + groups.get(b).critique.length) - (groups.get(a).promotes.length + groups.get(a).critique.length));
    main.innerHTML = `<h1>Handle with care</h1><p class="lede">Psychology's most-shared videos include some of its least reliable findings. These are still worth watching — they shaped the field and the conversation — but each comes with what happened next. The notes are PsychTube's, not the communities'.</p>
      ${order.map(id => { const c = PT.contested[id]; const g = groups.get(id); return `<section class="section care-list"><div class="section-head"><div><h2>${esc(c.name)}</h2><div class="sub" style="max-width:80ch;color:var(--ink-2)">${esc(c.note)} <span class="faint">${esc(c.source)}</span></div></div></div>${g.promotes.length ? grid(g.promotes) : ""}${g.critique.length ? `<h3 style="margin:14px 0 10px;color:var(--mint)">The pushback</h3>${grid(g.critique)}` : ""}</section>`; }).join("")}`;
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
      ${res.length ? `<div style="margin-top:14px">${res.map(v => card(v, { cls: "row-item", desc: true, chips: 4 })).join("")}</div>` : `<div class="empty"><p>Try a topic word (memory, Sapolsky, replication), a channel, or a person.</p></div>`}`;
  }
  function pageWatch(id, params) {
    const v = byId.get(id); if (!v) return notFound();
    setNav(""); setTitle(v.title);
    const start = parseInt(params.t || "0", 10) || 0;
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
    const instBox = v.inst && sameSeries ? `<div class="box inst"><h2>Published by ${esc(v.inst.n)}</h2><p>${esc(KIND_WORD[sameSeries.kind] === "talk" ? "Talk" : "Lecture")} ${v.inst.i} of ${v.inst.of} in <a href="#s-${sameSeries.id}">${esc(sameSeries.name)}</a>${sameSeries.lecturer ? `, taught by ${esc(sameSeries.lecturer)}` : ""}${sameSeries.year ? ` (${sameSeries.year})` : ""}; put online by ${esc(v.ch || sameSeries.ch || "")}. ${v.nrec ? "The communities below vouched for this lecture on its own, too." : "It's here on the institution's authority, not a forum's: no community has vouched for this particular lecture."}${sameSeries.note ? ` <span class="muted">${esc(sameSeries.note)}</span>` : ""}</p><p class="faint" style="margin:0"><a href="#s-${sameSeries.id}" style="text-decoration:underline">Whole course</a>${nextInSeries ? ` · <a href="#v-${nextInSeries}" style="text-decoration:underline">Next lecture</a>` : ""}${sameSeries.url ? ` · <a href="${esc(sameSeries.url)}" target="_blank" rel="noopener" style="text-decoration:underline">${sameSeries.provider === "panopto" ? "Course on Panopto" : "Playlist on YouTube"} ↗</a>` : ""}</p></div>` : "";
    const groupsByComm = new Map();
    for (const vo of v.vouches) { const arr = groupsByComm.get(vo.c) || []; arr.push(vo); groupsByComm.set(vo.c, arr); }
    const vouchHtml = [...groupsByComm.entries()].map(([comm, arr]) => arr.map((vo, i) => `<li>
        <div class="who">${i === 0 ? `<b>${esc(comm === "Psychology & Neuroscience SE" ? "Psych SE" : comm)}</b>` : ""}${esc(vo.a || "")}${vo.d ? `<br>${esc(vo.d.slice(0, 4))}` : ""}<br><span class="stance ${esc(vo.k)}">${esc(stanceLabel(vo.k))}</span></div>
        <div class="what"><div class="q">${vo.q ? "“" + esc(vo.q) + "”" : ""}${vo.t ? ` <a href="#v-${id}?t=${vo.t}" class="faint">at ${fmtDur(vo.t)}</a>` : ""}</div>${vo.thread ? `<div class="thread">in “${esc(vo.thread)}”</div>` : ""}${vo.u ? `<div class="thread"><a href="${esc(vo.u)}" target="_blank" rel="noopener">Open the original ↗</a></div>` : ""}</div>
      </li>`).join("")).join("");
    main.innerHTML = `<div class="watch"><div>
      ${LINKOUT
        ? `<a class="player poster" href="${watchUrl(v, start)}" target="_blank" rel="noopener" aria-label="Watch on ${providerOf(v)}">${ART || v.p ? (thumbUrl(v) ? `<img src="${thumbUrl(v)}" alt="" onerror="this.style.visibility='hidden'">` : "") : `<img src="https://i.ytimg.com/vi/${id}/hq720.jpg" alt="" data-step="0" onload="window.__ptPoster(this,'${id}')" onerror="window.__ptPoster(this,'${id}',true)">`}<span class="play"><span class="play-ic">▶</span>Watch on ${providerOf(v)}${start ? ` from ${fmtDur(start)}` : ""}</span></a><p class="faint" style="margin:8px 0 0;font-size:13px">${FROM_DISK ? "YouTube's player won't run inside a page opened from disk, so this copy links out. " : "This hosted copy can't embed players, so it links out. "}For playback right here in the page, use the live site: <a href="${SITE_URL}#v-${id}" target="_blank" rel="noopener" style="text-decoration:underline">${SITE_URL.replace(/^https:\/\//, "")}</a></p>`
        : `<div class="player"><iframe id="player" src="${embedUrl(v, start, state.settings.autoplay)}" title="${esc(v.title)}" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share; fullscreen" allowfullscreen referrerpolicy="strict-origin-when-cross-origin"></iframe></div>`}
      <h1>${esc(v.title)}</h1>
      <div class="meta"><span>${esc(v.ch || "")}</span>${v.len ? `<span>${fmtLen(v.len)}</span>` : ""}${v.pub ? `<span>uploaded ${v.approx ? "around " : ""}${v.pub.slice(0, 4)}</span>` : ""}${v.views ? `<span>${v.approx ? "~" : ""}${fmtViews(v.views)}</span>` : ""}${v.inst && sameSeries ? `<a class="chip inst" href="#s-${sameSeries.id}">${esc(instShort(v.inst.n))} · ${esc(sameSeries.name.length > 40 ? sameSeries.name.slice(0, 38) + "…" : sameSeries.name)}</a>` : ""}${v.topics.map(t => `<a class="chip" href="#t-${t}">${esc(topics.get(t) ? topics.get(t).name : t)}</a>`).join("")}</div>
      <div class="actions">
        <button class="btn" id="likeBtn" aria-pressed="${state.liked.has(id)}">♥ ${state.liked.has(id) ? "Liked" : "Like"}</button>
        <button class="btn" id="laterBtn" aria-pressed="${state.later.has(id)}">${state.later.has(id) ? "In watch later" : "Watch later"}</button>
        ${LINKOUT ? "" : `<a class="btn quiet" href="${watchUrl(v, start)}" target="_blank" rel="noopener">Open on ${providerOf(v)} ↗</a>`}
        <button class="btn quiet" id="copyBtn">${LINKOUT ? `Copy ${providerOf(v)} link` : "Copy link"}</button>
        ${nextInSeries ? `<a class="btn quiet" href="#v-${nextInSeries}">Next lecture →</a>` : ""}
      </div>
      ${c ? `<div class="box ${v.badge.role === "critique" ? "critique" : "care"}"><h2>${v.badge.role === "critique" ? "This video pushes back on: " : "Handle with care: "}${esc(c.name)}</h2><p>${esc(c.note)}</p><p class="faint" style="margin:0">${esc(c.source)}. <a href="#care" style="text-decoration:underline">All contested findings</a></p></div>` : ""}
      ${instBox}
      ${v.nmention ? `<div class="box"><h2>Why people recommend it</h2>${v.why ? `<p class="why">${esc(v.why)}</p>` : ""}${v.summary ? `<p class="muted">${esc(v.summary)}</p>` : ""}${v.quote ? `<p class="quote">“${esc(v.quote)}”</p>` : ""}
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
    main.querySelectorAll("[data-seek]").forEach(b => b.onclick = () => { const t = b.dataset.seek; document.getElementById("player").src = embedUrl(v, t, true); });
    window.scrollTo(0, 0);
  }
  const stanceLabel = k => ({ strong_rec: "strong rec", rec: "recommends", reference: "cites", critical: "critical", joke: "joke", comment: "comment", post: "post", question: "question", answer: "answer" }[k] || k);

  function pageLibrary(kind) {
    const map = { history: ["History", state.history.map(h => byId.get(h.id)).filter(Boolean), "What you've opened here, newest first. Stored only in this browser."], liked: ["Liked", [...state.liked].reverse().map(i => byId.get(i)).filter(Boolean), "Press l on any video to like it."], later: ["Watch later", [...state.later].reverse().map(i => byId.get(i)).filter(Boolean), "Press w on any video to save it for later."] };
    const [title, list, intro] = map[kind];
    setNav(kind); setTitle(title);
    main.innerHTML = `<h1>${title}</h1><p class="lede">${intro}</p>${list.length ? `<div class="toolbar"><button class="btn quiet" id="clearBtn">Clear ${title.toLowerCase()}</button></div>${grid(list)}` : `<div class="empty"><h2>Nothing here yet</h2><p>${kind === "history" ? "Open a video and it will show up here." : "Save a video and it will show up here."} <a href="#home" style="text-decoration:underline">Browse the home page</a>.</p></div>`}`;
    const cb = document.getElementById("clearBtn");
    if (cb) cb.onclick = () => { if (kind === "history") { state.history = []; store.set("history", []); } if (kind === "liked") { state.liked.clear(); store.set("liked", []); } if (kind === "later") { state.later.clear(); store.set("later", []); } route(); };
  }
  function pageData() {
    setNav("data"); setTitle("Data");
    const s = PT.stats;
    main.innerHTML = `<h1>The data</h1><div class="prose">
      <p class="lede">Everything behind PsychTube, free to reuse. Give it to your agent and build your own.</p>
      <div class="stats"><div><b>${s.videos.toLocaleString()}</b><span>videos</span></div><div><b>${s.mentions.toLocaleString()}</b><span>vouching comments</span></div><div><b>${s.communities}</b><span>communities</span></div><div><b>${s.inst ? s.inst.courses : PT.series.length}</b><span>${s.inst ? "university courses" : "lecture series"}</span></div>${s.inst ? `<div><b>${s.inst.lectures.toLocaleString()}</b><span>course lectures</span></div>` : ""}</div>
      ${ART ? `<p class="muted">This hosted copy can't hand out files. The export (<code>psychtube.json</code> + <code>DATA.md</code>) ships in the project folder next to the site, and the whole pipeline is there to rebuild it.</p>` : `<p><a class="btn primary" href="data/psychtube.json" download>Download psychtube.json</a> <a class="btn" href="data/DATA.md">Read DATA.md</a></p>`}
      <h2>Give it to your agent</h2>
      <p>Download the JSON, open your AI agent in that folder, and tell it what to build. For example:</p>
      <pre>Read DATA.md in this folder. Using psychtube.json, build me a small local web app that shows a weekly
syllabus of three psychology videos per topic area, lets me filter by length and course, and
remembers what I've watched.</pre>
      <h2>Where the vouches come from</h2>
      <ul>${Object.entries(s.sources).map(([k, n]) => `<li><b>${SRC_NAME[k]}</b>: ${n.toLocaleString()} mentions</li>`).join("")}</ul>
      <p>Hacker News mentions come from <a href="https://hackertube.org/data" target="_blank" rel="noopener" style="text-decoration:underline">HackerTube's export</a> (ODC-By, labeled by Claude). Reddit comments come from the Arctic Shift archive of psychology subreddits. Stack Exchange posts come from the Psychology &amp; Neuroscience site via its public API (CC BY-SA). Video titles, channels and lengths come from YouTube and belong to their creators. Topic labels, badges and notes were written by Claude and may contain mistakes.</p>
      ${s.inst && s.inst.courses ? `<p>Course lectures (<code>inst</code> on a video, <code>institutions</code> and the <code>series</code> entries with an <code>inst</code> field) come from ${s.inst.courses} public YouTube playlists on the channels of ${s.inst.institutions} universities and scientific institutions, pulled whole and kept in playlist order. Each lecture carries the institution, the course, its position and the playlist link; lectures no community vouched for have <code>nrec: 0</code>.</p>` : ""}
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
        <li><b>Flag the shaky stuff.</b> Videos that present a finding known to have shrunk or failed replication carry a “Handle with care” note with the follow-up research. Videos that push back get a “Debunk” mark.</li>
        ${PT.stats.inst && PT.stats.inst.courses ? `<li><b>Take the universities at their word.</b> A complete course that a university, one of its lecturers or a scientific institution published is institutional backing of a different kind, so the <a href="#courses" style="text-decoration:underline">Courses</a> hub carries ${PT.stats.inst.lectures.toLocaleString()} lectures from ${PT.stats.inst.courses} such playlists (MIT OpenCourseWare, Yale Courses, Stanford, the IITs via NPTEL, Gresham College, the Royal Institution, professors' own channels…), every lecture in order, whether or not a forum ever linked it. Those cards say “Published by” instead of a vouch count, and the lectures the communities <i>also</i> vouched for say both.</li>` : ""}
      </ul>
      <h2>What it deliberately lacks</h2>
      <ul><li>No accounts. History, likes and watch-later live in your browser.</li><li>No autoplay-next, no infinite feed. Rows end.</li><li>No uploader thumbnails by default. You see a frame from the middle of the video.</li></ul>
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
      <div class="setting"><div><b>Hide “handle with care” videos</b><p>Removes videos built on contested findings from every list except the Handle with care page.</p></div>${seg("hideCare", [[false, "Show"], [true, "Hide"]])}</div>
      <div class="setting"><div><b>Hide videos with content notes</b><p>Videos substantially about suicide, self-harm, eating disorders, abuse or substance use stay out of browsing rows. Search and direct links still work.</p></div>${seg("hideCW", [[true, "Hide"], [false, "Show"]])}</div>
      <div class="setting"><div><b>Your data</b><p>History, likes and watch-later are stored only in this browser.</p></div><button class="btn quiet" id="wipeBtn">Clear everything</button></div>`;
    main.querySelectorAll("[data-set]").forEach(b => b.onclick = () => { const val = b.dataset.val === "true" ? true : b.dataset.val === "false" ? false : b.dataset.val; s[b.dataset.set] = val; saveSettings(); applyTheme(); pageSettings(); });
    document.getElementById("wipeBtn").onclick = () => { ["history", "liked", "later"].forEach(k => store.set(k, [])); state.history = []; state.liked.clear(); state.later.clear(); toast("Cleared"); };
  }
  function notFound() { setTitle("Not found"); main.innerHTML = `<div class="empty"><h2>Not here</h2><p>That video or page isn't in the catalog. <a href="#home" style="text-decoration:underline">Back to the home page</a>.</p></div>`; }

  // ------------------------------------------------------------ actions
  function toast(msg) { const t = document.getElementById("toast"); t.textContent = msg; t.classList.add("on"); clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.remove("on"), 1600); }
  function toggleLike(id) { if (state.liked.has(id)) { state.liked.delete(id); toast("Removed from liked"); } else { state.liked.add(id); toast("Liked"); } store.set("liked", [...state.liked]); const b = document.getElementById("likeBtn"); if (b) { b.setAttribute("aria-pressed", state.liked.has(id)); b.textContent = `♥ ${state.liked.has(id) ? "Liked" : "Like"}`; } }
  function toggleLater(id) { if (state.later.has(id)) { state.later.delete(id); toast("Removed from watch later"); } else { state.later.add(id); toast("Saved for later"); } store.set("later", [...state.later]); const b = document.getElementById("laterBtn"); if (b) { b.setAttribute("aria-pressed", state.later.has(id)); b.textContent = state.later.has(id) ? "In watch later" : "Watch later"; } }

  // ------------------------------------------------------------ router
  let current = { page: "", id: "" };
  function route() {
    // routes are plain hash names: #home, #v-<id>, #t-<topic>, #a-<area>, #s-<series>, #q-<query>, #topics, #prefs ...
    // in-page filters ride along after "?" (e.g. #t-memory?sort=newest); legacy "#/v/<id>" links still work.
    let h = decodeURIComponent(location.hash.replace(/^#/, "")) || "home";
    if (h.startsWith("/")) { h = h.slice(1).replace(/^(v|t|a|s)\//, "$1-").replace(/^search\?q=/, "q-").replace(/^settings/, "prefs") || "home"; }
    const [path, qs] = h.split("?");
    const params = Object.fromEntries(new URLSearchParams(qs || ""));
    const m = /^(v|t|a|s|q)-(.+)$/.exec(path);
    const p0 = m ? m[1] : path;
    const arg = m ? m[2] : "";
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
    else if (p0 === "care") pageCare();
    else if (p0 === "longs") pageSimple("longs", "Longs", "Everything over an hour: full lectures, long interviews, documentaries. Where YouTube puts Shorts, PsychTube puts Longs.", V.filter(v => visible(v) && v.len >= 3600), params, "longs");
    else if (p0 === "canon") pageSimple("", "The canon", "The most vouched-for psychology videos across every community, by distinct recommenders.", V.filter(v => visible(v) && v.nrec > 0), params, "canon");
    else if (p0 === "history" || p0 === "liked" || p0 === "later") pageLibrary(p0);
    else if (p0 === "q") pageSearch({ q: arg });
    else if (p0 === "data") pageData();
    else if (p0 === "about") pageAbout();
    else if (p0 === "prefs") pageSettings();
    else notFound();
    if (p0 !== "v") window.scrollTo(0, 0);
  }
  window.addEventListener("hashchange", route);

  // ------------------------------------------------------------ search box
  const q = document.getElementById("q");
  document.getElementById("searchForm").addEventListener("submit", e => { e.preventDefault(); const val = q.value.trim(); if (val) location.hash = "#q-" + encodeURIComponent(val); });
  let typing;
  q.addEventListener("input", () => { clearTimeout(typing); typing = setTimeout(() => { const val = q.value.trim(); if (val.length >= 2) { history.replaceState(null, "", "#q-" + encodeURIComponent(val)); pageSearch({ q: val }); q.focus(); } }, 220); });

  // ------------------------------------------------------------ keyboard
  document.getElementById("themeBtn").onclick = () => { state.settings.theme = effectiveTheme() === "dark" ? "light" : "dark"; saveSettings(); applyTheme(); };
  document.getElementById("helpBtn").onclick = () => document.getElementById("helpDialog").showModal();
  document.addEventListener("keydown", e => {
    const inField = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName) || document.activeElement.isContentEditable;
    if (e.key === "Escape") { if (inField) { document.activeElement.blur(); return; } const d = document.getElementById("helpDialog"); if (d.open) { d.close(); return; } if (current.page) history.back(); return; }
    if (inField || e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.key === "/") { e.preventDefault(); q.focus(); q.select(); return; }
    if (e.key === "?") { document.getElementById("helpDialog").showModal(); return; }
    if (e.key === "t") { document.getElementById("themeBtn").click(); return; }
    const cards = [...main.querySelectorAll("a.card[data-id], .lectures a.lt")];
    const i = cards.indexOf(document.activeElement);
    if (e.key === "j" || e.key === "ArrowRight") { e.preventDefault(); const n = cards[Math.min(cards.length - 1, i + 1)]; if (n) { n.focus(); n.scrollIntoView({ block: "nearest", inline: "nearest" }); } return; }
    if (e.key === "k" || e.key === "ArrowLeft") { e.preventDefault(); const n = cards[Math.max(0, i - 1)]; if (n) { n.focus(); n.scrollIntoView({ block: "nearest", inline: "nearest" }); } return; }
    const focusedId = document.activeElement && document.activeElement.dataset ? document.activeElement.dataset.id : null;
    const target = current.page === "v" ? current.id : focusedId;
    if (e.key === "l" && target) { toggleLike(target); return; }
    if (e.key === "w" && target) { toggleLater(target); return; }
  });

  route();
})();
