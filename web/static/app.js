"use strict";
// Front end for web/server.py — plain JS, no build step.

const PLANETS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"];
const ABR = { Sun: "Su", Moon: "Mo", Mars: "Ma", Mercury: "Me", Jupiter: "Ju", Venus: "Ve",
              Saturn: "Sa", Rahu: "Ra", Ketu: "Ke", Ascendant: "As" };
const SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio",
               "Sagittarius", "Capricorn", "Aquarius", "Pisces"];
const SIGN_ABR = ["Ari", "Tau", "Gem", "Can", "Leo", "Vir", "Lib", "Sco", "Sag", "Cap", "Aqu", "Pis"];
const SIGN_LORD = ["Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury", "Venus", "Mars",
                   "Jupiter", "Saturn", "Saturn", "Jupiter"];
const DEFAULT = { name: "", gender: "", date: "1957-08-24", time: "13:55", city: "Liestal, Switzerland",
                  lat: 47.4833, lon: 7.7356, tz: 1, location: "Liestal, Switzerland" };

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const dmy = iso => { const [y, m, d] = iso.slice(0, 10).split("-"); return `${d}.${m}.${y}`; };
const deg = pos => pos.split("°")[0];          // "7° 48'" -> "7"

const state = { chart: null, params: null, style: "south", div: "d1", tab: "chart" };
const form = $("#form");

// ── prefs (per device) ──────────────────────────────────────────────────────
function pref(k, v) {
  try {
    if (v === undefined) return localStorage.getItem("pref_" + k);
    localStorage.setItem("pref_" + k, v);
  } catch { return null; }
}
function savedCharts() {
  try { return JSON.parse(localStorage.getItem("charts") || "{}"); } catch { return {}; }
}
function storeCharts(all) {
  try { localStorage.setItem("charts", JSON.stringify(all)); return true; } catch { return false; }
}

// ── form ────────────────────────────────────────────────────────────────────
function fillForm(p) {
  for (const k of ["name", "gender", "date", "time", "lat", "lon", "tz", "location"])
    if (form.elements[k]) form.elements[k].value = p[k] ?? "";
  form.elements.city.value = p.city ?? p.location ?? "";
}
function readForm() {
  const f = form.elements;
  return { name: f.name.value.trim(), gender: f.gender.value, date: f.date.value, time: f.time.value,
           lat: parseFloat(f.lat.value), lon: parseFloat(f.lon.value), tz: parseFloat(f.tz.value),
           location: f.location.value.trim(), city: f.city.value.trim() };
}

async function findPlace() {
  const f = form.elements, info = $("#place-info");
  const q = f.city.value.trim();
  if (q.length < 2) return false;
  info.className = "hint"; info.textContent = "Looking up…";
  const url = `api/place?q=${encodeURIComponent(q)}&date=${f.date.value || DEFAULT.date}` +
              `&time=${f.time.value || "12:00"}`;
  try {
    const r = await fetch(url);
    if (!r.ok) throw new Error(r.status === 404 ? "Place not found. Check the spelling or enter coordinates." : "Lookup failed.");
    const g = await r.json();
    f.lat.value = g.lat.toFixed(4); f.lon.value = g.lon.toFixed(4); f.tz.value = g.offset;
    f.location.value = g.label;
    info.className = "hint ok";
    info.textContent = `${g.label} · ${g.lat.toFixed(4)}°, ${g.lon.toFixed(4)}° · ${g.iana || ""} ${g.offset_str}` +
      (g.approx ? " · time zone estimated from longitude, please check" : "");
    form.dataset.placeFor = placeKey();
    return true;
  } catch (e) {
    info.className = "error"; info.textContent = e.message;
    return false;
  }
}
// the offset depends on date and time (summer time), so re-look-up when they change
const placeKey = () => [form.elements.city.value.trim().toLowerCase(), form.elements.date.value,
                        form.elements.time.value].join("|");

$("#btn-find").addEventListener("click", findPlace);
form.elements.city.addEventListener("keydown", e => {
  if (e.key === "Enter") { e.preventDefault(); findPlace(); }
});

form.addEventListener("submit", async e => {
  e.preventDefault();
  const err = $("#form-error"); err.hidden = true;
  if (form.elements.city.value.trim() && form.dataset.placeFor !== placeKey()) {
    if (!(await findPlace()) && !form.elements.lat.value) return;
  }
  const p = readForm();
  if ([p.lat, p.lon, p.tz].some(Number.isNaN)) {
    $("#coords").open = true;
    err.textContent = "Set a place first: find a city or enter coordinates."; err.hidden = false;
    return;
  }
  calculate(p);
});

// ── compute ─────────────────────────────────────────────────────────────────
async function calculate(p, { push = true } = {}) {
  const btn = $("#btn-calc"); btn.disabled = true; btn.textContent = "Calculating…";
  try {
    const r = await fetch("api/chart", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ date: p.date, time: p.time, lat: p.lat, lon: p.lon, tz: p.tz,
                             location: p.location, name: p.name, gender: p.gender }) });
    if (!r.ok) throw new Error("The server could not calculate this chart.");
    state.chart = await r.json(); state.params = p;
    if (push) history.replaceState(null, "", "#" + toHash(p));
    render();
  } catch (e) {
    const err = $("#form-error"); err.textContent = e.message; err.hidden = false;
    $("#form-card").hidden = false;
  } finally {
    btn.disabled = false; btn.textContent = "Calculate chart";
  }
}

function toHash(p) {
  return new URLSearchParams({ d: p.date, t: p.time, lat: p.lat, lon: p.lon, tz: p.tz,
                               loc: p.location || "", nm: p.name || "", g: p.gender || "" }).toString();
}
function fromHash() {
  const q = new URLSearchParams(location.hash.slice(1));
  if (!q.get("d") || !q.get("lat")) return null;
  return { date: q.get("d"), time: q.get("t") || "12:00", lat: +q.get("lat"), lon: +q.get("lon"),
           tz: +q.get("tz"), location: q.get("loc") || "", city: q.get("loc") || "",
           name: q.get("nm") || "", gender: q.get("g") || "" };
}

// ── render ──────────────────────────────────────────────────────────────────
function render() {
  const c = state.chart, p = state.params, pl = c.planets, cur = c.dashas.current;
  $("#form-card").hidden = true;
  $("#summary").hidden = false; $("#result").hidden = false;
  $("#s-name").textContent = p.name || "Chart";
  $("#s-birth").textContent = `${dmy(p.date)} ${p.time} · ${p.location || `${p.lat}, ${p.lon}`}`;
  const chips = [
    ["Lagna", `${c.lagna} ${c.lagna_pos}`],
    ["Moon", `${pl.Moon.sign} · ${pl.Moon.nakshatra} ${pl.Moon.pada}`],
    ["Sun", `${pl.Sun.sign} ${pl.Sun.pos}`],
    ["Dasha", [cur.maha, cur.antar, cur.pratyantar].filter(Boolean).join(" › ") || "—"],
  ];
  $("#chips").innerHTML = chips.map(([k, v]) => `<span class="chip">${k} <b>${esc(v)}</b></span>`).join("");
  document.title = `${p.name || "Chart"} · Vedic Birth Chart`;
  renderChartTab(); renderPlanets(); renderDasha(); renderTransits(); renderPanchang();
  showTab(state.tab);
}

function items(placement, planets, extraCls = "") {
  // group grahas by sign index for the chart renderers
  const by = Array.from({ length: 12 }, () => []);
  for (const n of ["Ascendant", ...PLANETS]) {
    const si = placement[n];
    if (si === undefined || si === null) continue;
    const rec = planets[n] || {};
    const showDeg = extraCls === "tr" || state.div === "d1";
    by[si].push({ n, txt: ABR[n], deg: showDeg && rec.pos ? deg(rec.pos) : "",
                  retro: !!rec.retrograde, cls: n === "Ascendant" ? "asc" : extraCls });
  }
  return by;
}

function renderChartTab() {
  const c = state.chart, pl = c.planets;
  const dv = state.div;
  const place = dv === "d1" ? Object.fromEntries(Object.entries(pl).map(([n, r]) => [n, r.sign_idx]))
                            : { ...c[dv], Ascendant: c[dv + "_lagna"] };
  const lagna = dv === "d1" ? c.lagna_idx : c[dv + "_lagna"];
  const title = { d1: "Rasi D1", d9: "Navamsa D9", d10: "Dasamsha D10", d3: "Drekkana D3" }[dv];
  $("#chart-box").innerHTML = chartSvg(items(place, pl), lagna, title, state.params.name || "");
  $("#chart-side").innerHTML = dv === "d1" ? planetTable(true)
    : `<p class="hint">${title}: each graha's sign in this division. Degrees are shown in the D1 chart.</p>`;
}

function chartSvg(by, lagna, title, sub) {
  return state.style === "north" ? northSvg(by, lagna, title) : southSvg(by, lagna, title, sub);
}

function label(it) {
  const r = it.retro && it.n !== "Rahu" && it.n !== "Ketu" ? `<tspan class="r">R</tspan>` : "";
  const d = it.deg !== "" ? ` <tspan class="c-deg">${it.deg}°</tspan>` : "";
  return `${it.txt}${r}${d}`;
}

// South Indian: fixed signs, Pisces top-left, running clockwise
const S_POS = { 11: [0, 0], 0: [1, 0], 1: [2, 0], 2: [3, 0], 3: [3, 1], 4: [3, 2],
                5: [3, 3], 6: [2, 3], 7: [1, 3], 8: [0, 3], 9: [0, 2], 10: [0, 1] };
function southSvg(by, lagna, title, sub) {
  let s = `<svg viewBox="0 0 400 400" role="img" aria-label="${esc(title)} chart, South Indian style">`;
  for (let si = 0; si < 12; si++) {
    const [cx, cy] = S_POS[si], x = cx * 100, y = cy * 100;
    s += `<rect x="${x}" y="${y}" width="100" height="100" class="c-cell${si === lagna ? " c-lagna" : ""}"/>`;
    if (si === lagna) s += `<line x1="${x}" y1="${y + 16}" x2="${x + 16}" y2="${y}" class="c-asc"/>`;
    s += `<text x="${x + 96}" y="${y + 14}" text-anchor="end" class="c-sign">${SIGN_ABR[si]}</text>`;
    const list = by[si], lh = Math.min(15, 70 / Math.max(list.length, 1));
    list.forEach((it, i) => {
      s += `<text x="${x + 7}" y="${y + 32 + i * lh}" class="c-pl${it.cls === "tr" ? " c-tr" : ""}"` +
           `${lh < 15 ? ` style="font-size:${Math.max(10, lh - 1)}px"` : ""}>${label(it)}</text>`;
    });
  }
  s += `<text x="200" y="195" text-anchor="middle" class="c-title">${esc(title)}</text>`;
  if (sub) s += `<text x="200" y="215" text-anchor="middle" class="c-sub">${esc(sub)}</text>`;
  return s + "</svg>";
}

// North Indian: fixed houses, Lagna in the top diamond, running anticlockwise
const N_TXT = [null, [200, 95], [100, 38], [38, 100], [100, 200], [38, 300], [100, 362],
               [200, 300], [300, 362], [362, 300], [300, 200], [362, 100], [300, 38]];
const N_NUM = [null, [200, 186], [100, 88], [86, 104], [186, 204], [86, 304], [100, 326],
               [200, 228], [300, 326], [314, 304], [214, 204], [314, 104], [300, 88]];
function northSvg(by, lagna, title) {
  let s = `<svg viewBox="0 0 400 400" role="img" aria-label="${esc(title)} chart, North Indian style">` +
    `<rect x="1" y="1" width="398" height="398" class="c-cell"/>` +
    `<path d="M200 1 L300 100 L200 200 L100 100 Z" class="c-lagna"/>` +
    `<path d="M1 1 L399 399 M399 1 L1 399 M200 1 L399 200 L200 399 L1 200 Z" class="c-line"/>`;
  for (let h = 1; h <= 12; h++) {
    const si = (lagna + h - 1) % 12, list = by[si];
    const [nx, ny] = N_NUM[h], [tx, ty] = N_TXT[h];
    s += `<text x="${nx}" y="${ny}" text-anchor="middle" class="c-sign">${si + 1}</text>`;
    const lh = [1, 4, 7, 10].includes(h) ? 15 : 13;
    const y0 = ty - ((list.length - 1) * lh) / 2 + 4;
    list.forEach((it, i) => {
      s += `<text x="${tx}" y="${y0 + i * lh}" text-anchor="middle" class="c-pl${it.cls === "tr" ? " c-tr" : ""}"` +
           `${lh < 15 ? ` style="font-size:12px"` : ""}>${label(it)}</text>`;
    });
  }
  return s + "</svg>";
}

function planetTable(compact) {
  const pl = state.chart.planets;
  const rows = ["Ascendant", ...PLANETS].map(n => {
    const p = pl[n], r = p.retrograde && !["Rahu", "Ketu"].includes(n) ? ` <span class="r">R</span>` : "";
    return `<tr><td>${n === "Ascendant" ? "Lagna" : n}${r}</td><td>${p.sign}</td><td class="num">${p.pos}</td>` +
      `<td>${p.nakshatra} ${p.pada}</td>` +
      (compact ? "" : `<td class="num">${p.house ?? 1}</td><td>${p.nak_lord}</td>`) +
      `<td class="muted">${n === "Ascendant" ? "" : esc(p.dignity)}</td></tr>`;
  }).join("");
  return `<div class="tbl"><table><thead><tr><th>Graha</th><th>Sign</th><th>Degree</th><th>Nakshatra</th>` +
    (compact ? "" : `<th>House</th><th>Nak. lord</th>`) + `<th>Dignity</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

function renderPlanets() {
  const c = state.chart;
  $("#planets").innerHTML = planetTable(false);
  const rows = [];
  for (let h = 1; h <= 12; h++) {
    const sign = c.houses[h], si = SIGNS.indexOf(sign);
    rows.push(`<tr><td class="num">${h}</td><td>${sign}</td><td>${SIGN_LORD[si]}</td>` +
              `<td>${(c.occupants[h] || []).join(", ") || "—"}</td></tr>`);
  }
  $("#houses").innerHTML = `<table><thead><tr><th>House</th><th>Sign</th><th>Lord</th><th>Occupants</th></tr></thead>` +
    `<tbody>${rows.join("")}</tbody></table>`;
}

function renderDasha() {
  const d = state.chart.dashas, cur = d.current;
  const act = d.mahadashas.find(m => m.active);
  const actA = act?.antardashas.find(a => a.active);
  const actP = actA?.pratyantardashas.find(x => x.active);
  $("#dasha-now").innerHTML = cur.maha
    ? `Now: <b>${cur.maha}</b> › <b>${cur.antar}</b> › <b>${cur.pratyantar}</b>` +
      (actP ? ` <span class="muted">until ${dmy(actP.end)}</span>` : "")
    : "No running period found.";
  const span = x => `<span class="d">${dmy(x.start)} – ${dmy(x.end)}</span>`;
  $("#dasha-tree").innerHTML = `<div class="dasha">` + d.mahadashas.map(m =>
    `<details class="${m.active ? "active" : ""}" ${m.active ? "open" : ""}>` +
      `<summary><span>${m.planet}</span>${span(m)}</summary><div class="lvl2">` +
      m.antardashas.map(a =>
        `<details class="${a.active ? "active" : ""}" ${a.active ? "open" : ""}>` +
          `<summary><span>${m.planet} / ${a.planet}</span>${span(a)}</summary><div class="lvl3">` +
          a.pratyantardashas.map(x =>
            `<div class="${x.active ? "active" : ""}"><span>${a.planet} / ${x.planet}</span>${span(x)}</div>`).join("") +
        `</div></details>`).join("") +
    `</div></details>`).join("") + `</div>`;
}

function renderTransits() {
  const c = state.chart, tr = c.transits, akv = c.ashtakavarga || {};
  $("#transit-when").textContent = `Positions for ${c.transit_local} (birthplace time zone), ` +
    `counted from the natal Lagna ${c.lagna}.`;
  const place = Object.fromEntries(PLANETS.filter(n => tr[n]).map(n => [n, tr[n].sign_idx]));
  const by = items(place, tr, "tr");
  $("#transit-box").innerHTML = chartSvg(by, c.lagna_idx, "Transits", c.transit_date);
  const rows = PLANETS.filter(n => tr[n]).map(n => {
    const t = tr[n], h = (t.sign_idx - c.lagna_idx + 12) % 12 + 1;
    const b = akv[n] ? akv[n][t.sign_idx] : "";
    const r = t.retrograde && !["Rahu", "Ketu"].includes(n) ? ` <span class="r">R</span>` : "";
    return `<tr><td>${n}${r}</td><td>${t.sign}</td><td class="num">${t.pos}</td><td class="num">${h}</td>` +
      `<td class="num">${b}</td><td class="muted">${t.sign_idx === c.planets[n].sign_idx ? "natal sign" : ""}</td></tr>`;
  }).join("");
  $("#transit-table").innerHTML = `<table><thead><tr><th>Graha</th><th>Sign</th><th>Degree</th>` +
    `<th>House</th><th>Bindus</th><th></th></tr></thead><tbody>${rows}</tbody></table>` +
    `<p class="hint">Bindus: Ashtakavarga points of that planet in the transited sign (4+ is supportive).</p>`;
}

function renderPanchang() {
  const pa = state.chart.panchang;
  const cells = [["Tithi", pa.tithi, `${pa.paksha} paksha · day ${pa.tithi_num} of 30 · ${pa.tithi_pct}% elapsed`],
                 ["Vara", pa.vara, `lord ${pa.vara_lord}`],
                 ["Nakshatra", pa.nakshatra, `lord ${pa.nakshatra_lord}`],
                 ["Yoga", pa.yoga, ""], ["Karana", pa.karana, ""]];
  $("#panchang").innerHTML = cells.map(([k, v, n]) =>
    `<div><small>${k}</small><b>${esc(v)}</b>${n ? `<small>${esc(n)}</small>` : ""}</div>`).join("");
}

// ── tabs & toggles ──────────────────────────────────────────────────────────
function showTab(t) {
  state.tab = t;
  $$("#tabs button").forEach(b => b.setAttribute("aria-selected", b.dataset.tab === t));
  $$(".panel").forEach(p => { p.hidden = p.dataset.panel !== t; });
}
$("#tabs").addEventListener("click", e => { const b = e.target.closest("button"); if (b) showTab(b.dataset.tab); });

function segment(id, key, after) {
  const el = $(id);
  const set = v => { state[key] = v; $$("button", el).forEach(b => b.setAttribute("aria-pressed", b.dataset.v === v)); };
  set(pref(key) || state[key]);
  el.addEventListener("click", e => {
    const b = e.target.closest("button"); if (!b) return;
    set(b.dataset.v); pref(key, b.dataset.v); if (state.chart) after();
  });
}
segment("#seg-style", "style", () => { renderChartTab(); renderTransits(); });
segment("#seg-div", "div", renderChartTab);

// ── summary actions, saved charts ───────────────────────────────────────────
$("#btn-edit").addEventListener("click", () => {
  $("#form-card").hidden = false; form.elements.name.focus();
});
$("#btn-new").addEventListener("click", () => {
  fillForm({ ...DEFAULT, name: "", city: "", location: "", lat: "", lon: "", tz: "" });
  $("#place-info").className = "hint"; $("#place-info").textContent = "Type a city and press Find.";
  delete form.dataset.placeFor;
  $("#form-card").hidden = false; form.elements.name.focus();
});
$("#home").addEventListener("click", e => { e.preventDefault(); window.scrollTo(0, 0); });

$("#btn-save").addEventListener("click", () => {
  const p = state.params, all = savedCharts();
  const key = prompt("Save this chart as", p.name || `Chart ${dmy(p.date)}`);
  if (!key) return;
  all[key.trim()] = { ...p, saved: new Date().toISOString() };
  alert(storeCharts(all) ? "Saved on this device." : "Could not save (browser storage is blocked).");
});

$("#btn-saved").addEventListener("click", () => {
  const all = savedCharts(), ul = $("#saved-list");
  const keys = Object.keys(all).sort((a, b) => a.localeCompare(b));
  ul.innerHTML = keys.length ? keys.map(k =>
    `<li><button data-open="${esc(k)}"><b>${esc(k)}</b><br><small class="muted">${dmy(all[k].date)} ${all[k].time} · ${esc(all[k].location)}</small></button>` +
    `<button data-del="${esc(k)}" aria-label="Delete ${esc(k)}">✕</button></li>`).join("")
    : `<li class="muted">Nothing saved yet. Calculate a chart and press Save.</li>`;
  $("#saved-dlg").showModal();
});
$("#saved-list").addEventListener("click", e => {
  const b = e.target.closest("button"); if (!b) return;
  const all = savedCharts();
  if (b.dataset.open) {
    const p = all[b.dataset.open]; fillForm(p); form.dataset.placeFor = placeKey();
    $("#saved-dlg").close(); calculate(p);
  } else if (b.dataset.del && confirm(`Delete "${b.dataset.del}"?`)) {
    delete all[b.dataset.del]; storeCharts(all); b.closest("li").remove();
  }
});

// ── start ───────────────────────────────────────────────────────────────────
const fromUrl = fromHash();
fillForm(fromUrl || DEFAULT);
form.dataset.placeFor = placeKey();                 // defaults already carry coordinates
if (fromUrl) calculate(fromUrl, { push: false });

if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
