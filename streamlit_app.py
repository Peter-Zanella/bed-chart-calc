#!/usr/bin/env python3
"""
Vedic Astrology (Jyotiṣa) Birth Chart — Streamlit web app.

Run locally:   streamlit run streamlit_app.py
Deploy free:   push to GitHub → share.streamlit.io → pick this file.

All calculations live in astro_engine.py; this file is purely the UI.
"""
from datetime import date, datetime, time as dtime

import streamlit as st

import astro_engine as E
from astro_engine import (
    SIGNS, SIGN_ABR, SIGN_LORDS, PLANET_ORDER, PLANET_ABR,
    NAKSHATRAS, _AKV_PLANETS, _SIGN_CELL,
)

# ──────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG + THEME
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Vedic Birth Chart", page_icon="✦", layout="wide")

st.markdown("""
<style>
  :root {
    --ink:#2b2118; --paper:#fbf7ef; --line:#d9c9a8;
    --accent:#7b2d26; --gold:#9a7b2e; --good:#2e7d4f; --warn:#b07d18; --bad:#9a342c;
  }
  .stApp { background: var(--paper); }
  h1,h2,h3,h4 { color: var(--ink); font-family: Georgia,'Times New Roman',serif; }
  .si-wrap { overflow-x:auto; }
  table.si { border-collapse:collapse; margin:0 auto; font-family:'DejaVu Sans Mono',monospace; }
  table.si td {
    border:1px solid var(--line); width:96px; height:96px; vertical-align:top;
    padding:4px 5px; background:#fff; font-size:11px; line-height:1.35;
  }
  table.si td.center {
    background:var(--paper); text-align:center; vertical-align:middle;
    font-family:Georgia,serif; color:var(--accent); font-size:14px; font-weight:bold;
  }
  table.si td.lagna { background:#fdf3df; box-shadow: inset 0 0 0 2px var(--gold); }
  .si-hdr { color:#8a7a5c; font-size:10px; letter-spacing:.3px; display:block; margin-bottom:2px; }
  .si-natal { color:var(--ink); font-weight:600; }
  .si-tr    { color:var(--accent); }
  .si-div   { border-top:1px dashed #c9b896; margin:2px 0; }
  .akv td,.akv th { border:1px solid var(--line); padding:4px 7px; text-align:center;
                    font-family:'DejaVu Sans Mono',monospace; font-size:12px; }
  .akv th { background:var(--paper); }
  .badge { display:inline-block; padding:2px 9px; border-radius:10px; font-size:12px;
           font-weight:600; color:#fff; }
  .b-good{background:var(--good);} .b-warn{background:var(--warn);} .b-bad{background:var(--bad);}
  .meta { font-family:'DejaVu Sans Mono',monospace; font-size:13px; color:var(--ink); }
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────────────
# SOUTH INDIAN CHART → HTML
# ──────────────────────────────────────────────────────────────────────────────
def _nak_idx(name: str) -> int:
    return next((i for i, (n, _) in enumerate(NAKSHATRAS) if n == name), 0)

def south_indian_html(planet_data, placements, lagna_si,
                      detail=False, transits=None) -> str:
    """Render a South Indian chart (fixed signs) as an HTML table."""
    natal = {i: [] for i in range(12)}
    trans = {i: [] for i in range(12)}
    for p, si in placements.items():
        if p != "Ascendant":
            natal[si].append(p)
    if transits:
        for p, pd in transits.items():
            if p != "Ascendant":
                trans[pd["sign_idx"]].append(p)

    def fmt(p, pd, cls):
        ab = PLANET_ABR.get(p, p[:2])
        if detail and pd:
            deg = int(pd["lon"] % 30); mn = int((pd["lon"] % 30 % 1) * 60)
            na = E.NAK_ABR[_nak_idx(pd.get("nakshatra", ""))]
            return f"<span class='{cls}'>{ab} {deg}°{mn:02d}' {na} p{pd.get('pada',1)}</span>"
        return f"<span class='{cls}'>{ab}</span>"

    def cell(si):
        house = (si - lagna_si) % 12 + 1
        is_l = si == lagna_si
        cls = "lagna" if is_l else ""
        hdr = f"{'◆ ' if is_l else ''}{SIGN_ABR[si]} · H{house}"
        body = "<br>".join(fmt(p, planet_data.get(p, {}), "si-natal") for p in natal[si])
        if natal[si] and trans[si]:
            body += "<div class='si-div'></div>"
        if trans[si]:
            body += "<br>".join(fmt(p, (transits or {}).get(p, {}), "si-tr") for p in trans[si])
        return f"<td class='{cls}'><span class='si-hdr'>{hdr}</span>{body}</td>"

    # build 4x4 grid; center is a single merged cell
    grid = {pos: si for si, pos in _SIGN_CELL.items()}
    rows = []
    rows.append("<tr>" + "".join(cell(grid[(0, c)]) for c in range(4)) + "</tr>")
    rows.append(
        f"<tr>{cell(grid[(1,0)])}"
        f"<td class='center' colspan='2' rowspan='2'>{_title}</td>"
        f"{cell(grid[(1,3)])}</tr>"
    )
    rows.append(f"<tr>{cell(grid[(2,0)])}{cell(grid[(2,3)])}</tr>")
    rows.append("<tr>" + "".join(cell(grid[(3, c)]) for c in range(4)) + "</tr>")
    return f"<div class='si-wrap'><table class='si'>{''.join(rows)}</table></div>"


_title = ""  # set just before each render (keeps the helper signature simple)

def render_south_indian(label, planet_data, placements, lagna_si, detail=False, transits=None):
    global _title
    _title = label
    st.markdown(
        south_indian_html(planet_data, placements, lagna_si, detail, transits),
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────────────────────
# SIDEBAR — BIRTH DETAILS
# ──────────────────────────────────────────────────────────────────────────────
st.sidebar.header("Birth details")

name = st.sidebar.text_input("Name", "")
gender = st.sidebar.selectbox("Gender", ["", "Male", "Female"])

bdate = st.sidebar.date_input(
    "Birth date", value=date(1957, 8, 24),
    min_value=date(1800, 1, 1), max_value=date(2100, 12, 31),
)
btime = st.sidebar.time_input("Birth time (local)", value=dtime(13, 55))

st.sidebar.divider()
mode = st.sidebar.radio("Location", ["Search by city", "Enter coordinates"], index=0)

city = lat = lon = tz_offset = loc_label = None
geo_info = None

if mode == "Search by city":
    city = st.sidebar.text_input("City", "Liestal, Switzerland")
    if st.sidebar.button("🔍 Look up location", use_container_width=True):
        with st.spinner("Geocoding & resolving timezone…"):
            geo_info = E.resolve_location(
                city, bdate.year, bdate.month, bdate.day, btime.hour, btime.minute
            )
        st.session_state["geo"] = geo_info
    geo_info = st.session_state.get("geo")
    if geo_info:
        if geo_info.get("offset") is None:
            st.sidebar.warning("Found the place but couldn't resolve the timezone — "
                               "switch to manual coordinates below.")
        else:
            lat, lon = geo_info["lat"], geo_info["lon"]
            tz_offset = geo_info["offset"]
            loc_label = geo_info["label"]
            st.sidebar.success(
                f"{loc_label}\n\n{lat:.4f}°, {lon:.4f}°\n\n"
                f"{geo_info.get('iana','?')} · {geo_info['offset_str']}"
            )
else:
    lat = st.sidebar.number_input("Latitude (N+)", value=47.4833, format="%.4f")
    lon = st.sidebar.number_input("Longitude (E+)", value=7.7356, format="%.4f")
    tz_offset = st.sidebar.number_input(
        "UTC offset (e.g. +1 CET, +5.5 IST)", value=1.0, step=0.5, format="%.2f"
    )
    loc_label = st.sidebar.text_input("Location label", "Liestal, Switzerland")

go = st.sidebar.button("✦ Generate chart", type="primary", use_container_width=True)


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────
st.title("✦ Vedic Astrology Birth Chart")
st.caption("Jyotiṣa · Lahiri Ayanamsha · Whole-Sign Houses")

if not go:
    st.info("Fill in the birth details on the left and press **Generate chart**. "
            "Use *Search by city* for automatic, historically-correct timezone handling.")
    st.stop()

if lat is None or lon is None or tz_offset is None:
    st.error("Location isn't set. Search a city (then it auto-fills) or switch to manual coordinates.")
    st.stop()

with st.spinner("Computing positions, dashas, ashtakavarga…"):
    chart = E.generate_chart(
        bdate.year, bdate.month, bdate.day, btime.hour, btime.minute,
        lat, lon, tz_offset, loc_label or "", name, gender,
    )

m = chart["meta"]

# ── Summary header ────────────────────────────────────────────────────────────
top = st.columns([2, 1, 1, 1])
top[0].metric("Lagna (Ascendant)", f"{chart['lagna']} {chart['lagna_pos']}")
top[1].metric("Moon sign", chart["planets"]["Moon"]["sign"])
top[2].metric("Nakshatra", chart["planets"]["Moon"]["nakshatra"])
cur = chart["dashas"]["current"]
top[3].metric("Current Mahadasha", cur["maha"] or "—")

with st.expander("Chart metadata", expanded=False):
    g = f"  ({m['gender']})" if m.get("gender") else ""
    st.markdown(
        f"<div class='meta'>"
        f"Name : {m.get('name') or '—'}{g}<br>"
        f"Birth : {m['birth']}  ({m['tz']})<br>"
        f"UT : {m['ut']}<br>"
        f"Location : {m['location'] or '—'}<br>"
        f"Coordinates : {m['lat']:.4f}° N / {m['lon']:.4f}° E<br>"
        f"Julian Day : {m['jd']}<br>"
        f"Ayanamsha : {m['ayan']}° (Lahiri)<br>"
        f"Engine : {m['engine']}"
        f"</div>", unsafe_allow_html=True,
    )

tabs = st.tabs(["Planets & Houses", "Divisional charts", "Ashtakavarga",
                "Varshaphala", "Vimshottari Dasha"])

# ── Tab 1: planets + houses ───────────────────────────────────────────────────
with tabs[0]:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Graha (Planets)")
        rows = []
        for nm in PLANET_ORDER:
            p = chart["planets"][nm]
            rows.append({
                "Planet": nm, "Sign": p["sign"], "Pos": p["pos"],
                "H": p.get("house", "—"), "Nakshatra": p["nakshatra"],
                "Pada": p["pada"], "Lord": p["nak_lord"], "Dignity": p["dignity"],
            })
        st.dataframe(rows, hide_index=True, use_container_width=True)
    with c2:
        st.subheader("Bhava (Houses)")
        rows = []
        for h in range(1, 13):
            sign = chart["houses"][h]
            rows.append({
                "House": h, "Sign": sign, "Lord": SIGN_LORDS[sign],
                "Occupants": ", ".join(chart["occupants"][h]) or "—",
            })
        st.dataframe(rows, hide_index=True, use_container_width=True)

# ── Tab 2: divisional charts ──────────────────────────────────────────────────
with tabs[1]:
    st.caption(f"South Indian (fixed signs · ◆ = Lagna). "
               f"Black = natal · red = transit ({chart['transit_date']}).")
    d1_pl = {p: chart["planets"][p]["sign_idx"] for p in chart["planets"]}
    g1, g2 = st.columns(2)
    with g1:
        render_south_indian("D1 Rasi", chart["planets"], d1_pl, chart["lagna_idx"],
                            detail=True, transits=chart["transits"])
        st.write("")
        render_south_indian("D3 Drekkana", chart["planets"], chart["d3"], chart["d3_lagna"])
    with g2:
        render_south_indian("D9 Navamsa", chart["planets"], chart["d9"], chart["d9_lagna"])
        st.write("")
        render_south_indian("D10 Dasamsha", chart["planets"], chart["d10"], chart["d10_lagna"])

# ── Tab 3: ashtakavarga ───────────────────────────────────────────────────────
with tabs[2]:
    akv = chart["ashtakavarga"]; lagna = chart["lagna_idx"]

    def color(v, sarva=False):
        if sarva:
            return "var(--good)" if v >= 30 else "var(--warn)" if v >= 26 else "var(--bad)"
        return "var(--good)" if v >= 6 else "var(--warn)" if v >= 4 else "var(--bad)"

    hdr = "".join(f"<th>{s}</th>" for s in SIGN_ABR)
    html = f"<table class='akv'><tr><th></th>{hdr}<th>Σ</th></tr>"
    for p in _AKV_PLANETS:
        row = akv[p]; nat = chart["planets"][p]["sign_idx"]
        cells = ""
        for s in range(12):
            bold = "font-weight:800;text-decoration:underline;" if s == nat else ""
            cells += f"<td style='color:{color(row[s])};{bold}'>{row[s]}</td>"
        html += f"<tr><th style='text-align:left'>{p}</th>{cells}<td><b>{sum(row)}</b></td></tr>"
    sarva = akv["Sarva"]
    scells = "".join(f"<td style='color:{color(v,True)};font-weight:700'>{v}</td>" for v in sarva)
    html += f"<tr><th style='text-align:left'>SARVA</th>{scells}<td><b>{sum(sarva)}</b></td></tr>"
    html += "</table>"
    st.subheader("Bhinna + Sarvashtakavarga")
    st.markdown(html, unsafe_allow_html=True)
    st.caption("Green ≥ threshold · amber mid · red low. Underlined = planet's own natal sign. "
               "Sarva thresholds: ≥30 strong, 26–29 average, ≤25 weak.")

    st.subheader(f"Transit strength ({chart['transit_date']})")
    tr = chart["transits"]; rows = []
    for p in _AKV_PLANETS:
        row = akv[p]; nat = chart["planets"][p]["sign_idx"]
        tsi = tr.get(p, {}).get("sign_idx", nat); b = row[tsi]
        strength = "■ strong" if b >= 5 else "□ average" if b >= 4 else "✗ weak"
        rows.append({"Planet": p, "Natal sign": SIGNS[nat], "Transit sign": SIGNS[tsi],
                     "House": (tsi - lagna) % 12 + 1, "Bindus": b, "Strength": strength})
    st.dataframe(rows, hide_index=True, use_container_width=True)

# ── Tab 4: varshaphala ────────────────────────────────────────────────────────
with tabs[3]:
    vp = chart["varshaphala"]
    a, b, c = st.columns(3)
    a.metric(f"Year {vp['year_number']}", f"{vp['target_year']}–{vp['target_year']+1}")
    b.metric("Annual Lagna", f"{vp['lagna']} {vp['lagna_pos']}")
    c.metric("Varsha Pati (Year Lord)", vp["varsha_pati"])
    st.markdown(
        f"<div class='meta'>Solar return : {vp['return_dt_utc']} &nbsp;·&nbsp; "
        f"Muntha : <b>{vp['muntha_sign']}</b> (lord {vp['muntha_lord']}) &nbsp;·&nbsp; "
        f"Weekday lord {vp['weekday_lord']} / Hora lord {vp['hora_lord']} / "
        f"Lagna lord {vp['lagna_lord']}</div>", unsafe_allow_html=True,
    )
    st.write("")
    cc1, cc2 = st.columns([3, 2])
    with cc1:
        sr_pl = {p: vp["planets"][p]["sign_idx"] for p in vp["planets"]}
        render_south_indian("Varshaphala", vp["planets"], sr_pl, vp["lagna_si"], detail=True)
    with cc2:
        rows = []
        for nm in PLANET_ORDER:
            p = vp["planets"].get(nm)
            if not p:
                continue
            natal = chart["planets"][nm]["sign_idx"]
            rows.append({"Planet": nm, "Sign": p["sign"], "Pos": p["pos"],
                         "H": (p["sign_idx"] - vp["lagna_si"]) % 12 + 1,
                         "Dignity": p["dignity"],
                         "↔natal": "✓" if p["sign_idx"] == natal else ""})
        st.dataframe(rows, hide_index=True, use_container_width=True)
    sarva = vp["ashtakavarga"]["Sarva"]; mun = vp["muntha_si"]; mb = sarva[mun]
    badge = ("b-good", "strong") if mb >= 30 else ("b-warn", "average") if mb >= 26 else ("b-bad", "weak")
    st.markdown(f"Muntha (**{vp['muntha_sign']}**) annual Sarva bindus: "
                f"<span class='badge {badge[0]}'>{mb} · {badge[1]}</span>",
                unsafe_allow_html=True)

# ── Tab 5: dasha ──────────────────────────────────────────────────────────────
with tabs[4]:
    dd = chart["dashas"]; mahas = dd["mahadashas"]
    mo = chart["planets"]["Moon"]
    st.caption(f"Moon {mo['sign']} {mo['pos']} · {mo['nakshatra']} (lord {mo['nak_lord']})")
    if cur["maha"]:
        st.success(f"**Today:** Mahadasha **{cur['maha']}** → "
                   f"Antardasha **{cur['antar']}** → Pratyantardasha **{cur['pratyantar']}**")

    fmt = lambda dt: dt.strftime("%d %b %Y")
    st.subheader("Mahadashas")
    st.dataframe(
        [{"Planet": md["planet"], "Start": fmt(md["start"]), "End": fmt(md["end"]),
          "Years": round(md["years"], 1), "Active": "◄" if md["active"] else ""}
         for md in mahas],
        hide_index=True, use_container_width=True,
    )

    active = next((md for md in mahas if md["active"]), None)
    if active:
        st.subheader(f"Antardashas in {active['planet']} Mahadasha")
        st.dataframe(
            [{"Antardasha": f"{active['planet']} / {ad['planet']}",
              "Start": fmt(ad["start"]), "End": fmt(ad["end"]),
              "Years": round(ad["years"], 2), "Active": "◄" if ad["active"] else ""}
             for ad in active["antardashas"]],
            hide_index=True, use_container_width=True,
        )
        aad = next((ad for ad in active["antardashas"] if ad["active"]), None)
        if aad:
            st.subheader(f"Pratyantardashas in {active['planet']} / {aad['planet']}")
            st.dataframe(
                [{"Pratyantardasha": f"{active['planet']} / {aad['planet']} / {pad['planet']}",
                  "Start": fmt(pad["start"]), "End": fmt(pad["end"]),
                  "Years": round(pad["years"], 3), "Active": "◄" if pad["active"] else ""}
                 for pad in aad["pratyantardashas"]],
                hide_index=True, use_container_width=True,
            )

st.divider()
st.caption("For study and reflection. Calculations match Prokerala / astro.com when "
           "pyswisseph or JPL Horizons is available; otherwise ~0.5° built-in fallback.")
