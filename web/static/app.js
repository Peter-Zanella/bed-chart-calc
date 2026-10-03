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

const state = { chart: null, params: null, style: "south", div: "d1", tab: "chart", loaded: {} };
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

async function lookupPlace(q, date, time) {
  const r = await fetch(`api/place?q=${encodeURIComponent(q)}&date=${date}&time=${time}`);
  if (!r.ok) throw new Error(r.status === 404 ? "Place not found. Check the spelling or enter coordinates." : "Lookup failed.");
  return r.json();
}
async function postJSON(url, body) {
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" },
                               body: JSON.stringify(body) });
  if (!r.ok) throw new Error("The server could not calculate this.");
  return r;
}
const chartBody = p => ({ date: p.date, time: p.time, lat: p.lat, lon: p.lon, tz: p.tz,
                          location: p.location || "", name: p.name || "", gender: p.gender || "" });

async function findPlace() {
  const f = form.elements, info = $("#place-info");
  const q = f.city.value.trim();
  if (q.length < 2) return false;
  info.className = "hint"; info.textContent = "Looking up…";
  try {
    const g = await lookupPlace(q, f.date.value || DEFAULT.date, f.time.value || "12:00");
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
    const r = await postJSON("api/chart", chartBody(p));
    state.chart = await r.json(); state.params = p; state.loaded = {}; state.match = null;
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
  $("#s-question").hidden = !p.question;
  $("#s-question").textContent = p.question ? `Question: ${p.question}` : "";
  document.title = `${p.name || "Chart"} · Vedic Birth Chart`;
  state.varsha = c.varshaphala;
  $("#match-result").innerHTML = "";
  $$(".sub.svc").forEach(el => { el.innerHTML = `<p class="hint">Loading…</p>`; });
  renderChartTab(); renderPlanets(); renderYogas(); renderAkv(); renderVarsha(); renderDasha();
  renderJaimini(); renderTransits(); renderPanchang(); renderShadbala();
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
  const title = { d1: "Rasi D1", d9: "Navamsa D9", d10: "Dasamsha D10", d3: "Drekkana D3",
                  d4: "Chaturthamsha D4" }[dv];
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
  renderUpagrahas();
  const rows = [];
  for (let h = 1; h <= 12; h++) {
    const sign = c.houses[h], si = SIGNS.indexOf(sign);
    rows.push(`<tr><td class="num">${h}</td><td>${sign}</td><td>${SIGN_LORD[si]}</td>` +
              `<td>${(c.occupants[h] || []).join(", ") || "—"}</td></tr>`);
  }
  $("#houses").innerHTML = `<table><thead><tr><th>House</th><th>Sign</th><th>Lord</th><th>Occupants</th></tr></thead>` +
    `<tbody>${rows.join("")}</tbody></table>`;
}

// ── Ashtakavarga ────────────────────────────────────────────────────────────
const AKV_PLANETS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"];
const grade = (v, sarva) => v >= (sarva ? 30 : 5) ? "good" : v >= (sarva ? 26 : 4) ? "avg" : "weak";

// a chart grid with one big number per sign (Sarvashtakavarga)
function numberSvg(values, lagna, title, sub) {
  const empty = Array.from({ length: 12 }, () => []);
  let svg = chartSvg(empty, lagna, title, sub).replace("</svg>", "");
  for (let si = 0; si < 12; si++) {
    let x, y;
    if (state.style === "north") { [x, y] = N_TXT[(si - lagna + 12) % 12 + 1]; y += 8; }
    else { const [cx, cy] = S_POS[si]; x = cx * 100 + 50; y = cy * 100 + 66; }
    svg += `<text x="${x}" y="${y}" text-anchor="middle" class="c-num ${grade(values[si], true)}">${values[si]}</text>`;
  }
  return svg + "</svg>";
}

function akvTable(akv, natal) {
  const head = `<tr><th></th>${SIGN_ABR.map(a => `<th>${a}</th>`).join("")}<th>Σ</th></tr>`;
  const rows = AKV_PLANETS.map(p => `<tr><td>${p}</td>` + akv[p].map((v, si) =>
      `<td class="${grade(v)}${natal && natal[p] === si ? " nat" : ""}">${v}</td>`).join("") +
    `<td>${akv[p].reduce((a, b) => a + b, 0)}</td></tr>`).join("");
  const sarva = `<tr class="total"><td>Sarva</td>` + akv.Sarva.map(v =>
    `<td class="${grade(v, true)}">${v}</td>`).join("") + `<td>${akv.Sarva.reduce((a, b) => a + b, 0)}</td></tr>`;
  return `<table class="akv">${head}${rows}${sarva}</table>`;
}

function renderAkv() {
  const c = state.chart, akv = c.ashtakavarga, tr = c.transits;
  $("#akv-box").innerHTML = numberSvg(akv.Sarva, c.lagna_idx, "Sarvashtakavarga", "");
  const natal = Object.fromEntries(AKV_PLANETS.map(p => [p, c.planets[p].sign_idx]));
  $("#akv-table").innerHTML = akvTable(akv, natal);
  const rows = AKV_PLANETS.map(p => {
    const si = tr[p].sign_idx, b = akv[p][si];
    return `<tr><td>${p}</td><td>${SIGNS[si]}</td><td class="num">${(si - c.lagna_idx + 12) % 12 + 1}</td>` +
      `<td class="num ${grade(b)}">${b}</td><td class="num">${akv.Sarva[si]}</td></tr>`;
  }).join("");
  $("#akv-transit").innerHTML = `<h2>Transits today</h2><table><thead><tr><th>Planet</th><th>Transit sign</th>` +
    `<th>House</th><th>Bindus</th><th>Sarva</th></tr></thead><tbody>${rows}</tbody></table>`;
}

// ── Varshaphala ─────────────────────────────────────────────────────────────
function renderVarsha() {
  const v = state.varsha, p = state.params;
  const vy = $("#vy");
  vy.value = v.target_year; vy.min = +p.date.slice(0, 4); vy.max = vy.min + 120;
  const mb = v.ashtakavarga.Sarva[v.muntha_si];
  const cells = [
    [`Year ${v.year_number}`, `${v.target_year}–${v.target_year + 1}`, `Solar return ${v.return_dt_utc}`],
    ["Annual Lagna", `${v.lagna} ${v.lagna_pos}`, `lord ${v.lagna_lord}`],
    ["Varsha Pati (year lord)", v.varsha_pati, `weekday ${v.weekday_lord} · hora ${v.hora_lord}`],
    ["Muntha", v.muntha_sign, `lord ${v.muntha_lord} · ${mb} Sarva points (${grade(mb, true) === "good" ? "strong" : grade(mb, true) === "avg" ? "average" : "weak"})`],
  ];
  $("#varsha-kv").innerHTML = cells.map(([k, val, n]) =>
    `<div><small>${k}</small><b>${esc(val)}</b><small>${esc(n)}</small></div>`).join("");
  const place = Object.fromEntries(Object.entries(v.planets).map(([n, r]) => [n, r.sign_idx]));
  const prevDiv = state.div; state.div = "d1";        // show degrees
  $("#varsha-box").innerHTML = chartSvg(items(place, v.planets), v.lagna_si, "Varshaphala", String(v.target_year));
  state.div = prevDiv;
  const rows = PLANETS.map(n => {
    const r = v.planets[n], same = r.sign_idx === state.chart.planets[n].sign_idx;
    const rt = r.retrograde && !["Rahu", "Ketu"].includes(n) ? ` <span class="r">R</span>` : "";
    return `<tr><td>${n}${rt}</td><td>${r.sign}</td><td class="num">${r.pos}</td>` +
      `<td class="num">${(r.sign_idx - v.lagna_si + 12) % 12 + 1}</td><td class="muted">${esc(r.dignity)}</td>` +
      `<td class="muted">${same ? "natal sign" : ""}</td></tr>`;
  }).join("");
  $("#varsha-table").innerHTML = `<table><thead><tr><th>Graha</th><th>Sign</th><th>Degree</th><th>House</th>` +
    `<th>Dignity</th><th></th></tr></thead><tbody>${rows}</tbody></table>`;
}

async function loadVarsha(year) {
  const p = state.params, min = +p.date.slice(0, 4);
  year = Math.max(min, Math.min(min + 120, year | 0));
  if (!year || year === state.varsha.target_year) { renderVarsha(); return; }
  try {
    const r = await fetch("api/chart", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ date: p.date, time: p.time, lat: p.lat, lon: p.lon, tz: p.tz, varsha_year: year }) });
    if (!r.ok) throw new Error();
    state.varsha = (await r.json()).varshaphala; renderVarsha();
  } catch { $("#vy").value = state.varsha.target_year; }
}
$("#vy").addEventListener("change", e => loadVarsha(+e.target.value));
$("#vy-prev").addEventListener("click", () => loadVarsha(state.varsha.target_year - 1));
$("#vy-next").addEventListener("click", () => loadVarsha(state.varsha.target_year + 1));

// ── Yogas, upagrahas ────────────────────────────────────────────────────────
function renderYogas() {
  const ys = state.chart.yogas || [];
  const order = ["Pancha Mahapurusha", "Raja", "Dhana", "Vipareeta Raja", "Sun", "Moon", "Varga", "Other"];
  const rank = g => { const i = order.indexOf(g); return i < 0 ? 99 : i; };
  const groups = [...new Set(ys.map(y => y.group))].sort((a, b) => rank(a) - rank(b));
  $("#yogas").innerHTML = !ys.length ? `<p class="muted">None of the checked yogas are present.</p>` :
    `<p><b>${ys.length}</b> yogas found</p>` + groups.map(g =>
      `<h2>${esc(g)}</h2><ul class="list">` + ys.filter(y => y.group === g).map(y =>
        `<li><b>${esc(y.name)}</b> <span class="muted">${esc(y.planets.join(", "))}</span><br>${esc(y.detail)}</li>`).join("") +
      `</ul>`).join("");
}

function renderUpagrahas() {
  const c = state.chart, rows = [];
  for (const [n, r] of Object.entries(c.upagrahas || {}))
    rows.push(`<tr><td>${esc(r.name || n)}</td><td>${r.sign}</td><td class="num">${r.pos}</td>` +
              `<td>${r.nakshatra} ${r.pada}</td><td class="num">${r.house}</td></tr>`);
  for (const [n, r] of Object.entries(c.outer_planets || {}))
    rows.push(`<tr><td>${n}${r.retrograde ? ` <span class="r">R</span>` : ""}</td><td>${r.sign}</td>` +
              `<td class="num">${r.pos}</td><td>${r.nakshatra} ${r.pada}</td><td class="num">${r.house}</td></tr>`);
  $("#upagrahas").innerHTML = rows.length ? `<table><thead><tr><th>Point</th><th>Sign</th><th>Degree</th>` +
    `<th>Nakshatra</th><th>House</th></tr></thead><tbody>${rows.join("")}</tbody></table>` : "";
}

// ── Jaimini ─────────────────────────────────────────────────────────────────
const KARAKA = { Atmakaraka: ["AK", "soul / self"], Amatyakaraka: ["AmK", "career / advisor"],
  Bhratrikaraka: ["BK", "siblings"], Matrikaraka: ["MK", "mother"], Pitrikaraka: ["PiK", "father"],
  Putrakaraka: ["PuK", "children"], Gnatikaraka: ["GK", "cousins / obstacles"], Darakaraka: ["DK", "spouse"] };

function renderJaimini() {
  const c = state.chart, j = c.jaimini, cd = c.chara_dasha;
  const kv = [["Atmakaraka", j.atmakaraka, "soul"], ["Darakaraka", j.darakaraka, "spouse"],
              ["Karakamsha", j.karakamsha, `lord ${j.karakamsha_lord}`],
              ["Arudha Lagna", j.arudha_lagna, `lord ${j.arudha_lagna_lord}`],
              ["Upapada Lagna", j.upapada_lagna, `lord ${j.upapada_lagna_lord}`]];
  $("#jaimini-kv").innerHTML = kv.map(([k, v, n]) => `<div><small>${k}</small><b>${esc(v)}</b><small>${esc(n)}</small></div>`).join("");
  const place = Object.fromEntries(PLANETS.map(n => [n, c.planets[n].sign_idx]));
  const by = items(place, c.planets);
  by[j.arudha_lagna_si].push({ n: "AL", txt: "AL", deg: "", cls: "asc" });
  by[j.upapada_lagna_si].push({ n: "UL", txt: "UL", deg: "", cls: "asc" });
  const prev = state.div; state.div = "d1";
  $("#jaimini-box").innerHTML = chartSvg(by, c.lagna_idx, "Rasi + AL / UL", "");
  state.div = prev;
  $("#jaimini-table").innerHTML = `<table><thead><tr><th>Karaka</th><th>Planet</th><th>Degree in sign</th></tr></thead><tbody>` +
    j.order.map(r => { const k = j.karakas[r];
      return `<tr><td>${KARAKA[r][0]} · ${r}<br><small class="muted">${KARAKA[r][1]}</small></td><td>${k.planet}</td>` +
        `<td class="num">${k.deg_in_sign.toFixed(2)}°${k.reverse ? ` <small class="muted">(30° − deg: ${k.effective.toFixed(2)}°)</small>` : ""}</td></tr>`;
    }).join("") + `</tbody></table><p class="hint">8-karaka scheme; Rahu is counted in reverse (30° minus its degree).</p>`;

  $("#chara-note").textContent = `Starts at the Lagna sign; direction ${cd.direction}.` +
    (Object.keys(cd.colords || {}).length ? " Dual-lord signs: " + Object.entries(cd.colords)
      .map(([s, v]) => `${s} → ${v.lord} (${v.reason})`).join("; ") + "." : "");
  const act = cd.mahadashas.find(m => m.active), aad = act?.antardashas.find(a => a.active);
  $("#chara-now").innerHTML = act ? `Now: <b>${act.sign}</b>${aad ? ` › <b>${aad.sign}</b>` : ""}` +
    (aad ? ` <span class="muted">until ${dmy(aad.end)}</span>` : "") : "No running period found.";
  const span = x => `<span class="d">${dmy(x.start)} – ${dmy(x.end)}</span>`;
  $("#chara-tree").innerHTML = `<div class="dasha">` + cd.mahadashas.slice(0, 12).map(m =>
    `<details class="${m.active ? "active" : ""}" ${m.active ? "open" : ""}><summary><span>${m.sign} ` +
    `<small class="muted">${m.years} y</small></span>${span(m)}</summary><div class="lvl3">` +
    m.antardashas.map(a => `<div class="${a.active ? "active" : ""}"><span>${m.sign} / ${a.sign}</span>${span(a)}</div>`).join("") +
    `</div></details>`).join("") + `</div>`;
}

// ── Shad Bala ───────────────────────────────────────────────────────────────
function bars(rows, max) {
  // rows: [label, value, required|null, note]
  return `<div class="bars">` + rows.map(([l, v, req, note]) => {
    const ok = req == null || v >= req;
    return `<div class="bar"><span class="bl">${l}</span><span class="bt"><span class="bf ${ok ? "ok" : "low"}" ` +
      `style="width:${Math.min(100, v / max * 100)}%"></span>` +
      (req != null ? `<span class="bm" style="left:${req / max * 100}%" title="required ${req}"></span>` : "") +
      `</span><span class="bv">${v.toFixed(2)}${note ? ` <small class="muted">${note}</small>` : ""}</span></div>`;
  }).join("") + `</div>`;
}

function renderShadbala() {
  const sb = state.chart.shadbala, bb = state.chart.bhavabala;
  if (!sb) return;
  const P = sb.planets, order = sb.order;
  const max = Math.max(...order.map(p => Math.max(P[p].rupa, P[p].required))) * 1.05;
  $("#sb-bars").innerHTML = bars(order.map(p => [p, P[p].rupa, P[p].required,
                                                 `${Math.round(P[p].ratio * 100)}%`]), max);
  $("#sb-table").innerHTML = `<table><thead><tr><th>Planet</th><th>Sthana</th><th>Dig</th><th>Kala</th>` +
    `<th>Cheshta</th><th>Naisargika</th><th>Drik</th><th>Total</th><th>Ishta</th><th>Kashta</th></tr></thead><tbody>` +
    order.map(p => { const x = P[p];
      return `<tr><td>${p}</td>${[x.sthana, x.dig, x.kala, x.cheshta, x.naisargika, x.drik, x.total, x.ishta, x.kashta]
        .map(v => `<td class="num">${v ?? "—"}</td>`).join("")}</tr>`; }).join("") +
    `</tbody></table><p class="hint">Values in virupas. Ishta = benefic yield, Kashta = difficult yield (0 to 60).</p>`;
  if (bb) {
    const H = bb.houses, hmax = Math.max(...Object.values(H).map(h => h.rupa)) * 1.05;
    $("#bb-bars").innerHTML = bars(Array.from({ length: 12 }, (_, i) => {
      const h = H[i + 1]; return [`H${i + 1} ${SIGN_ABR[SIGNS.indexOf(h.sign)]}`, h.rupa, null, h.lord]; }), hmax);
  }
}

// ── German sections from astro-report-service ───────────────────────────────
async function loadSection(name) {
  const el = $(`.sub[data-subpanel="${name}"]`);
  try {
    const r = await postJSON(`api/section/${name}`, chartBody(state.params));
    el.innerHTML = (await r.json()).html.replaceAll("rgba(255,255,255,.14)", "var(--line)");
  } catch (e) {
    state.loaded[name] = false;
    el.innerHTML = `<p class="error">${esc(e.message)}</p>`;
  }
}

// ── Muhurta ─────────────────────────────────────────────────────────────────
const MUH_COL = { good: "good", mix: "avg", fair: "avg", bad: "weak", excellent: "good" };
async function loadMuhurta() {
  const sel = $("#muh-act");
  if (!sel.options.length) {
    try {
      state.activities = await (await fetch("api/muhurta/activities")).json();
      sel.innerHTML = Object.keys(state.activities).map(a => `<option>${esc(a)}</option>`).join("");
      sel.value = pref("muh_act") || sel.options[0].value;
    } catch { state.loaded.muhurta = false; return; }
  }
  const act = sel.value, p = state.params, months = +$("#muh-months").value, min = +$("#muh-min").value;
  $("#muh-naks").textContent = `Favourable nakshatras for ${act}: ${state.activities[act].join(", ")}.`;
  $("#muh-rows").innerHTML = `<p class="hint">Calculating…</p>`;
  try {
    const today = new Date().toISOString().slice(0, 10);
    const d = await (await postJSON("api/muhurta", { activity: act, lat: p.lat, lon: p.lon, tz: p.tz,
                                                     start: today, days: months * 31 })).json();
    const g = d.grid, rowsDef = [["Nakshatra", "nak", "nak_label"], ["Weekday", "vara", "weekday"],
      ["Tithi", "tithi", "tithi_label"], ["Yoga", "yoga", "yoga_label"], ["Karana", "karana", "karana_label"],
      ["Overall", "overall", null]];
    $("#muh-grid").innerHTML = `<table class="heat"><tr><td></td>${g.map(r => `<th>${r.wd}<br>${r.dom}</th>`).join("")}</tr>` +
      rowsDef.map(([n, k, lab]) => `<tr><td>${n}</td>` + g.map(r =>
        `<td class="h ${MUH_COL[r[k]] || ""}" title="${esc(lab ? r[lab] : r.overall)}">` +
        (k === "overall" ? ({ excellent: "E", good: "G", fair: "F", bad: "✗" }[r[k]] || "") : "") + `</td>`).join("") +
        `</tr>`).join("") + `</table>`;
    const rows = d.rows.filter(r => r.score >= min);
    $("#muh-rows").innerHTML = !rows.length ? `<p class="muted">No matching windows. Try more months or a lower filter.</p>` :
      `<table><thead><tr><th>Date</th><th>Window</th><th>Nakshatra</th><th>Tithi</th><th>Rating</th><th>Caveats</th></tr></thead><tbody>` +
      rows.map(r => `<tr><td>${dmy(r.date)} <small class="muted">${r.weekday.slice(0, 3)}</small></td><td>${esc(r.window)}</td>` +
        `<td>${esc(r.nakshatra)}</td><td>${esc(r.tithi)}</td><td class="${r.score >= 3 ? "good" : r.score >= 2 ? "" : "avg"}">${esc(r.rating)}</td>` +
        `<td class="muted">${esc(r.flags)}</td></tr>`).join("") + `</tbody></table>`;
  } catch (e) {
    state.loaded.muhurta = false;
    $("#muh-rows").innerHTML = `<p class="error">${esc(e.message)}</p>`;
  }
}
["#muh-act", "#muh-months", "#muh-min"].forEach(id => $(id).addEventListener("change", () => {
  pref("muh_act", $("#muh-act").value); loadMuhurta();
}));

// ── Eclipses ────────────────────────────────────────────────────────────────
async function loadEclipses(year) {
  year = year || state.eclipseYear || new Date().getFullYear();
  const input = $("#ey");
  try {
    const d = await (await fetch(`api/eclipses?start=${year}&end=${year}`)).json();
    year = Math.max(d.range[0], Math.min(d.range[1], year));
    state.eclipseYear = year; input.value = year; input.min = d.range[0]; input.max = d.range[1];
    const list = d.years[year] || [];
    const natal = Object.entries(state.chart.lons);
    $("#eclipses").innerHTML = !list.length ? `<p class="muted">No eclipses in ${year}.</p>` :
      `<table><thead><tr><th>Date</th><th>Kind</th><th>Position</th><th>Nakshatra</th><th>Hits</th><th>Visible</th></tr></thead><tbody>` +
      list.map(e => {
        const hits = natal.filter(([, l]) => Math.abs(((e.lon - l + 540) % 360) - 180) <= 3)
          .map(([n]) => n === "Ascendant" ? "Lagna" : n);
        return `<tr><td>${String(e.day).padStart(2, "0")}.${String(e.month).padStart(2, "0")}.${e.year} ` +
          `<small class="muted">${e.time_ut || ""} UT</small></td><td>${e.kind === "solar" ? "☀ Solar" : "☾ Lunar"}<br>` +
          `<small class="muted">${esc(e.type || "")}</small></td><td>${esc(e.sign)} ${esc(e.deg_str)}</td>` +
          `<td>${esc(e.nakshatra)} ${e.pada}</td><td class="${hits.length ? "weak" : "muted"}">${hits.join(", ") || "—"}</td>` +
          `<td>${e.visible_wadenswil ? "yes" : "no"}</td></tr>`;
      }).join("") + `</tbody></table>`;
  } catch {
    state.loaded.eclipses = false;
    $("#eclipses").innerHTML = `<p class="error">Could not load the eclipse list.</p>`;
  }
}
$("#ey").addEventListener("change", e => loadEclipses(+e.target.value));
$("#ey-prev").addEventListener("click", () => loadEclipses(state.eclipseYear - 1));
$("#ey-next").addEventListener("click", () => loadEclipses(state.eclipseYear + 1));

// ── Compatibility ───────────────────────────────────────────────────────────
$("#match-form").addEventListener("submit", async e => {
  e.preventDefault();
  const f = e.target.elements, err = $("#match-error"), btn = $("button[type=submit]", e.target);
  err.hidden = true; btn.disabled = true; btn.textContent = "Checking…";
  try {
    const g = await lookupPlace(f.city.value.trim(), f.date.value, f.time.value || "12:00");
    const partner = { date: f.date.value, time: f.time.value || "12:00", lat: g.lat, lon: g.lon, tz: g.offset,
                      location: g.label, name: f.name.value.trim() || "Partner" };
    const v = await (await postJSON("api/compat", { a: chartBody(state.params), b: chartBody(partner),
                                                   male: f.male.value })).json();
    state.match = { partner, male: f.male.value };
    renderMatch(v);
  } catch (ex) {
    err.textContent = ex.message; err.hidden = false;
  } finally {
    btn.disabled = false; btn.textContent = "Check compatibility";
  }
});

function renderMatch(v) {
  const cls = { exc: "good", good: "good", ok: "avg" }[v.verdict_class] || "weak";
  const dosh = v.doshas.map(d => `<li class="${d.active ? "weak" : "muted"}"><b>${esc(d.name)} dosha</b> ` +
    `${d.active ? "present" : "present but cancelled"}: ${esc(d.reason)}</li>`).join("");
  const ma = v.mangal_a, mb = v.mangal_b;
  const mang = ma.manglik && mb.manglik ? "Both are Manglik, which traditionally cancels out."
    : ma.manglik || mb.manglik ? `Only ${esc(ma.manglik ? v.a.name : v.b.name)} is Manglik.` : "Neither partner is Manglik.";
  $("#match-result").innerHTML =
    `<p style="margin-top:1rem"><b>${esc(v.a.name)}</b> (Moon ${esc(v.a.moon)}) and <b>${esc(v.b.name)}</b> ` +
    `(Moon ${esc(v.b.moon)}, ${esc(v.b.loc)})</p>` +
    `<div class="kv"><div><small>Guna Milan</small><b class="${cls}">${v.total} / ${v.max}</b><small>${esc(v.verdict)} · 18 is the usual minimum</small></div></div>` +
    `<div class="tbl"><table><thead><tr><th>Kuta</th><th>Score</th><th>Meaning</th></tr></thead><tbody>` +
    v.kutas.map(k => `<tr><td>${esc(k.name)}</td><td class="num">${k.got} / ${k.max}</td><td class="muted wrap">${esc(k.note)}</td></tr>`).join("") +
    `</tbody></table></div>` +
    (dosh ? `<h2>Doshas</h2><ul class="list">${dosh}</ul>` : `<p class="good">No Nadi or Bhakoot dosha.</p>`) +
    `<h2>Additional factors</h2><ul class="list">` + v.extra.map(x =>
      `<li><b>${x.ok ? "✓" : "⚠"} ${esc(x.name)}</b>: ${esc(x.verdict)}</li>`).join("") + `</ul>` +
    `<h2>Mangal dosha</h2><p>${mang}</p><p class="hint">${esc(v.a.name)}: ${esc(ma.note)} · ${esc(v.b.name)}: ${esc(mb.note)}</p>` +
    `<p class="hint">The PDF now includes this compatibility report.</p>`;
}

// ── PDF ─────────────────────────────────────────────────────────────────────
$("#btn-pdf").addEventListener("click", async () => {
  const b = $("#btn-pdf"); b.disabled = true; b.textContent = "PDF…";
  try {
    const body = { chart: chartBody(state.params) };
    if (state.match) { body.partner = chartBody(state.match.partner); body.male = state.match.male; }
    const blob = await (await postJSON("api/pdf", body)).blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `vedic-chart-${(state.params.name || "chart").replace(/[^\w]+/g, "_")}.pdf`;
    document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 10000);
  } catch (e) {
    alert(e.message);
  } finally {
    b.disabled = false; b.textContent = "PDF";
  }
});

// ── Prashna ─────────────────────────────────────────────────────────────────
$("#btn-prashna").addEventListener("click", () => {
  $("#prashna-error").hidden = true;
  const f = $("#prashna-form").elements;
  f.city.value = f.city.value || pref("here") || "";
  $("#prashna-dlg").showModal();
});
$("#prashna-form").addEventListener("submit", async e => {
  e.preventDefault();
  const f = e.target.elements, err = $("#prashna-error");
  err.hidden = true;
  try {
    const now = new Date(), iso = now.toISOString();
    const g = await lookupPlace(f.city.value.trim(), iso.slice(0, 10), iso.slice(11, 16));
    pref("here", f.city.value.trim());
    // the moment "now" expressed in the place's local time
    const local = new Date(now.getTime() + g.offset * 3600e3).toISOString();
    const p = { date: local.slice(0, 10), time: local.slice(11, 16), lat: g.lat, lon: g.lon, tz: g.offset,
                location: g.label, city: g.label, name: "Prashna", gender: "", question: f.q.value.trim() };
    $("#prashna-dlg").close();
    fillForm(p); form.dataset.placeFor = placeKey();
    state.tab = "chart";
    await calculate(p);
  } catch (ex) {
    err.textContent = ex.message; err.hidden = false;
  }
});

// ── Birth time rectification ────────────────────────────────────────────────
const RT_COLS = [["lagna", "Lagna"], ["d9", "D9"], ["d10", "D10"], ["d3", "D3"], ["d4", "D4"], ["moon_nak", "Moon"]];
const fmtMin = m => m >= 60 ? `${Math.floor(m / 60)} h ${Math.round(m % 60)} min` : `${m < 10 ? m.toFixed(1) : Math.round(m)} min`;

// local date and time shifted by whole minutes (calendar arithmetic only, the UTC offset stays)
function shiftTime(p, min) {
  const [y, mo, d] = p.date.split("-").map(Number), [h, mi] = p.time.split(":").map(Number);
  const t = new Date(Date.UTC(y, mo - 1, d, h, mi + min)).toISOString();
  return { ...p, date: t.slice(0, 10), time: t.slice(11, 16) };
}
function useTime(p) {
  fillForm(p); form.dataset.placeFor = placeKey();
  calculate(p);
}

async function loadRectify() {
  const p = state.params, span = +$("#rt-span").value, step = +$("#rt-step").value;
  $("#rt-time").textContent = p.time;
  $("#rt-rows").innerHTML = `<p class="hint">Calculating…</p>`;
  try {
    const r = await (await postJSON("api/rectify", { ...chartBody(p), span, step })).json();
    $("#rt-factors").innerHTML = r.factors.map(f => {
      const near = Math.min(f.minus ?? Infinity, f.plus ?? Infinity);
      const hold = f.from || f.to
        ? `holds ${f.from || "…"} – ${f.to || "…"}` +
          ` (${f.minus != null ? "−" + fmtMin(f.minus) : "beyond"} / ${f.plus != null ? "+" + fmtMin(f.plus) : "beyond"})`
        : `steady across ± ${fmtMin(r.span)}`;
      return `<div><small>${esc(f.label)}</small><b>${esc(f.value)}</b>` +
             `<small class="${near < 5 ? "weak" : near < 15 ? "avg" : ""}">${hold}</small></div>`;
    }).join("");
    $("#rt-changes-h").textContent = `Changes within ± ${fmtMin(r.span)}`;
    $("#rt-changes").innerHTML = !r.changes.length ? `<p class="muted">Nothing changes in this window.</p>` :
      `<table><thead><tr><th>Time</th><th>Offset</th><th>What changes</th><th></th></tr></thead><tbody>` +
      r.changes.map(c => `<tr><td>${c.at}${c.date !== p.date ? ` <small>${dmy(c.date)}</small>` : ""}</td>` +
        `<td class="num">${c.offset > 0 ? "+" : ""}${c.offset.toFixed(1)} min</td><td>${esc(c.label)}</td>` +
        `<td>${esc(c.from)} → <b>${esc(c.to)}</b></td></tr>`).join("") + `</tbody></table>`;
    const head = `<tr><th>Time</th>${RT_COLS.map(([, l]) => `<th>${l}</th>`).join("")}<th>Dasha balance</th><th>Running now</th></tr>`;
    let prev = null;
    const rows = r.rows.map(x => {
      const chg = k => prev && prev[k] !== x[k] ? " chg" : "";
      const cells = RT_COLS.map(([k]) => k === "lagna"
        ? `<td class="${chg(k)}">${x.lagna} <small class="muted">${x.lagna_pos}</small></td>`
        : `<td class="${chg(k)}">${esc(x[k])}</td>`).join("");
      const out = `<tr class="${x.offset === 0 ? "cur" : ""}"><td><button class="link" data-rt="${x.date} ${x.time}">${x.time}</button>` +
        `${x.date !== p.date ? ` <small class="muted">${dmy(x.date)}</small>` : ""}</td>${cells}` +
        `<td>${esc(x.balance)}</td><td>${esc(x.now)}${x.antar_start ? ` <small class="muted">since ${dmy(x.antar_start)}</small>` : ""}</td></tr>`;
      prev = x; return out;
    }).join("");
    $("#rt-rows").innerHTML = `<table class="rect"><thead>${head}</thead><tbody>${rows}</tbody></table>`;
  } catch (e) {
    state.loaded.rectify = false;
    $("#rt-rows").innerHTML = `<p class="error">${esc(e.message)}</p>`;
  }
}
$("#rt-span").addEventListener("change", () => { pref("rt_span", $("#rt-span").value); loadRectify(); });
$("#rt-step").addEventListener("change", loadRectify);
$("#rt-span").value = pref("rt_span") || "15";
$$("[data-nudge]").forEach(b => b.addEventListener("click", () => useTime(shiftTime(state.params, +b.dataset.nudge))));
$("#rt-rows").addEventListener("click", e => {
  const b = e.target.closest("[data-rt]"); if (!b) return;
  const [date, time] = b.dataset.rt.split(" ");
  useTime({ ...state.params, date, time });
});
$("#btn-rectify").addEventListener("click", () => {
  showTab("more"); showSub($('.panel[data-panel="more"]'), "rectify");
  $("#result").scrollIntoView({ behavior: "smooth" });
});

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
  const panel = $(`.panel[data-panel="${t}"]`), on = panel && $(".subtabs [aria-pressed=true]", panel);
  if (on) loadSub(on.dataset.sub);
}
function showSub(panel, sub) {
  $$(".subtabs button", panel).forEach(b => b.setAttribute("aria-pressed", b.dataset.sub === sub));
  $$(".sub", panel).forEach(el => { el.hidden = el.dataset.subpanel !== sub; });
  loadSub(sub);
}
document.addEventListener("click", e => {
  const b = e.target.closest(".subtabs button");
  if (b) showSub(b.closest(".panel"), b.dataset.sub);
});
// sections that need their own request are fetched the first time they are opened
function loadSub(sub) {
  if (!state.chart || state.loaded[sub]) return;
  const run = { medical: loadSection, fixstars: loadSection, remedies: loadSection,
                muhurta: loadMuhurta, eclipses: () => loadEclipses(), rectify: loadRectify }[sub];
  if (!run) return;
  state.loaded[sub] = true;
  run(sub);
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
segment("#seg-style", "style", () => { renderChartTab(); renderTransits(); renderAkv(); renderVarsha(); renderJaimini(); });
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

if ("serviceWorker" in navigator) {
  // reload once when a new version takes over, so the page matches the new scripts
  const had = !!navigator.serviceWorker.controller;
  let reloaded = false;
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (had && !reloaded) { reloaded = true; location.reload(); }
  });
  navigator.serviceWorker.register("sw.js", { updateViaCache: "none" })
    .then(r => r.update()).catch(() => {});
}
