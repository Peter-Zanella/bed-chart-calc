#!/usr/bin/env python3
"""
Vedic Astrology (Jyotiṣa) Birth Chart — Streamlit web app.

Run locally:   streamlit run streamlit_app.py
Deploy free:   push to GitHub → share.streamlit.io → pick this file.

Calculations live in astro_engine.py; chart drawing in charts.py;
PDF in pdf_report.py; save/load in storage.py. This file is the UI.
"""
from datetime import date, time as dtime

import streamlit as st

import astro_engine as E
import charts
import pdf_report
import storage
from astro_engine import SIGNS, SIGN_LORDS, PLANET_ORDER, _AKV_PLANETS, SIGN_ABR

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
# CACHED COMPUTE
# ──────────────────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def compute(params: dict):
    return E.generate_chart(**params)

@st.cache_data(show_spinner=False)
def make_pdf(params: dict) -> bytes:
    return pdf_report.build_pdf(compute(params))


def draw_chart(style, label, planet_data, placements, lagna_si, detail=False, transits=None):
    if style == "North Indian":
        st.markdown(
            charts.north_indian_svg(label, planet_data, placements, lagna_si, detail),
            unsafe_allow_html=True)
    else:
        st.markdown(
            charts.south_indian_html(label, planet_data, placements, lagna_si, detail, transits),
            unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────────────
# FORM DEFAULTS  (a nonce in the widget keys lets "Load" reset the inputs cleanly)
# ──────────────────────────────────────────────────────────────────────────────
DEFAULTS = {"name": "", "gender": "", "date": date(1957, 8, 24), "time": dtime(13, 55),
            "city": "Liestal, Switzerland", "lat": 47.4833, "lon": 7.7356, "tz": 1.0,
            "label": "Liestal, Switzerland", "mode": "Search by city"}
fd = {**DEFAULTS, **st.session_state.get("form_defaults", {})}
n = st.session_state.setdefault("nonce", 0)
k = lambda name: f"{name}_{n}"   # versioned widget key


def load_entry(key, entry):
    d = storage.to_form_defaults(entry)
    st.session_state["form_defaults"] = d
    st.session_state["nonce"] = st.session_state.get("nonce", 0) + 1
    st.session_state["active_params"] = dict(
        year=d["date"].year, month=d["date"].month, day=d["date"].day,
        hour=d["time"].hour, minute=d["time"].minute,
        lat=d["lat"], lon=d["lon"], tz_offset=d["tz"],
        location=d["label"], name=d["name"], gender=d["gender"])
    st.session_state.pop("geo", None)
    st.rerun()


# ──────────────────────────────────────────────────────────────────────────────
# SIDEBAR — saved charts
# ──────────────────────────────────────────────────────────────────────────────
saved = storage.load_all()
with st.sidebar.expander(f"📂 Saved charts ({len(saved)})", expanded=bool(saved)):
    if not saved:
        st.caption("None yet — generate a chart, then **Save** it below.")
    for key, entry in saved.items():
        c1, c2, c3 = st.columns([5, 2, 2])
        c1.markdown(f"**{key}**<br><span style='font-size:11px;color:#8a7a5c'>"
                    f"{entry['date']} · {entry.get('label','')}</span>", unsafe_allow_html=True)
        if c2.button("Load", key=f"load_{key}", use_container_width=True):
            load_entry(key, entry)
        if c3.button("🗑", key=f"del_{key}", use_container_width=True):
            storage.delete(key); st.rerun()

# ──────────────────────────────────────────────────────────────────────────────
# SIDEBAR — birth details
# ──────────────────────────────────────────────────────────────────────────────
st.sidebar.header("Birth details")
name = st.sidebar.text_input("Name", fd["name"], key=k("name"))
gender = st.sidebar.selectbox("Gender", ["", "Male", "Female"],
                              index=["", "Male", "Female"].index(fd["gender"]), key=k("gender"))
bdate = st.sidebar.date_input("Birth date", value=fd["date"],
                              min_value=date(1800, 1, 1), max_value=date(2100, 12, 31), key=k("date"))
btime = st.sidebar.time_input("Birth time (local)", value=fd["time"], step=60, key=k("time"))

st.sidebar.divider()
mode = st.sidebar.radio("Location", ["Search by city", "Enter coordinates"],
                        index=["Search by city", "Enter coordinates"].index(fd["mode"]), key=k("mode"))

lat = lon = tz_offset = loc_label = None
if mode == "Search by city":
    city = st.sidebar.text_input("City", fd["city"], key=k("city"))
    if st.sidebar.button("🔍 Look up location", use_container_width=True):
        with st.spinner("Geocoding & resolving timezone…"):
            st.session_state["geo"] = E.resolve_location(
                city, bdate.year, bdate.month, bdate.day, btime.hour, btime.minute)
    geo = st.session_state.get("geo")
    if geo:
        if geo.get("offset") is None:
            st.sidebar.warning("Found the place but couldn't resolve the timezone — "
                               "use manual coordinates instead.")
        else:
            lat, lon, tz_offset, loc_label = geo["lat"], geo["lon"], geo["offset"], geo["label"]
            st.sidebar.success(f"{loc_label}\n\n{lat:.4f}°, {lon:.4f}°\n\n"
                               f"{geo.get('iana','?')} · {geo['offset_str']}")
else:
    lat = st.sidebar.number_input("Latitude (N+)", value=fd["lat"], format="%.4f", key=k("lat"))
    lon = st.sidebar.number_input("Longitude (E+)", value=fd["lon"], format="%.4f", key=k("lon"))
    tz_offset = st.sidebar.number_input("UTC offset (+1 CET, +5.5 IST)", value=fd["tz"],
                                        step=0.5, format="%.2f", key=k("tz"))
    loc_label = st.sidebar.text_input("Location label", fd["label"], key=k("label"))

if st.sidebar.button("✦ Generate chart", type="primary", use_container_width=True):
    if lat is None or lon is None or tz_offset is None:
        st.sidebar.error("Set a location first (look up a city or enter coordinates).")
    else:
        st.session_state["active_params"] = dict(
            year=bdate.year, month=bdate.month, day=bdate.day,
            hour=btime.hour, minute=btime.minute,
            lat=lat, lon=lon, tz_offset=tz_offset,
            location=loc_label or "", name=name, gender=gender)


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────
st.title("✦ Vedic Astrology Birth Chart")
st.caption("Jyotiṣa · Lahiri Ayanamsha · Whole-Sign Houses")

ap = st.session_state.get("active_params")
if not ap:
    st.info("Enter birth details on the left and press **Generate chart**. "
            "Use *Search by city* for automatic, historically-correct timezones.")
    st.stop()

with st.spinner("Computing positions, dashas, ashtakavarga…"):
    chart = compute(ap)
m = chart["meta"]
cur = chart["dashas"]["current"]

# ── header metrics + actions ─────────────────────────────────────────────────
top = st.columns([2, 1, 1, 1])
top[0].metric("Lagna (Ascendant)", f"{chart['lagna']} {chart['lagna_pos']}")
top[1].metric("Moon sign", chart["planets"]["Moon"]["sign"])
top[2].metric("Nakshatra", chart["planets"]["Moon"]["nakshatra"])
top[3].metric("Current Mahadasha", cur["maha"] or "—")

a1, a2, a3 = st.columns([3, 2, 3])
with a1:
    default_key = ap["name"] or f"Chart {ap['year']}-{ap['month']:02d}-{ap['day']:02d}"
    save_key = st.text_input("Save as", default_key, label_visibility="collapsed",
                             placeholder="name this chart")
with a2:
    if st.button("💾 Save chart", use_container_width=True):
        ok = storage.save(save_key.strip() or default_key, dict(
            name=ap["name"], gender=ap["gender"],
            date=f"{ap['year']:04d}-{ap['month']:02d}-{ap['day']:02d}",
            time=f"{ap['hour']:02d}:{ap['minute']:02d}",
            lat=ap["lat"], lon=ap["lon"], tz=ap["tz_offset"], label=ap["location"]))
        st.toast("Saved ✓" if ok else "Couldn't write file (read-only filesystem).")
        st.rerun()
with a3:
    try:
        pdf_bytes = make_pdf(ap)
        st.download_button("⬇ Download PDF", pdf_bytes,
                           file_name=f"vedic-chart-{(ap['name'] or 'chart').replace(' ','_')}.pdf",
                           mime="application/pdf", use_container_width=True)
    except Exception as e:
        st.caption(f"PDF export unavailable ({e}). Ensure reportlab is installed.")

with st.expander("Chart metadata"):
    g = f"  ({m['gender']})" if m.get("gender") else ""
    st.markdown(f"<div class='meta'>Name : {m.get('name') or '—'}{g}<br>"
                f"Birth : {m['birth']}  ({m['tz']})<br>UT : {m['ut']}<br>"
                f"Location : {m['location'] or '—'}<br>"
                f"Coordinates : {m['lat']:.4f}° N / {m['lon']:.4f}° E<br>"
                f"Julian Day : {m['jd']}<br>Ayanamsha : {m['ayan']}° (Lahiri)<br>"
                f"Engine : {m['engine']}</div>", unsafe_allow_html=True)

style = st.radio("Chart style", ["South Indian", "North Indian"],
                 horizontal=True, key="chart_style")

tabs = st.tabs(["Planets & Houses", "Divisional charts", "Ashtakavarga",
                "Varshaphala", "Vimshottari Dasha", "Jaimini"])

# ── Tab 1 ─────────────────────────────────────────────────────────────────────
with tabs[0]:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Graha (Planets)")
        st.dataframe([{"Planet": nm, "Sign": p["sign"], "Pos": p["pos"],
                       "H": p.get("house", "—"), "Nakshatra": p["nakshatra"],
                       "Pada": p["pada"], "Lord": p["nak_lord"], "Dignity": p["dignity"]}
                      for nm in PLANET_ORDER for p in [chart["planets"][nm]]],
                     hide_index=True, use_container_width=True)
    with c2:
        st.subheader("Bhava (Houses)")
        st.dataframe([{"House": h, "Sign": chart["houses"][h],
                       "Lord": SIGN_LORDS[chart["houses"][h]],
                       "Occupants": ", ".join(chart["occupants"][h]) or "—"}
                      for h in range(1, 13)], hide_index=True, use_container_width=True)

# ── Tab 2 ─────────────────────────────────────────────────────────────────────
with tabs[1]:
    note = "Black = natal · red = transit ({}).".format(chart["transit_date"]) \
        if style == "South Indian" else "Fixed houses · signs rotate · Lagna at top-center."
    st.caption(f"{style} · ◆/⬩La = Lagna. {note}")
    d1 = {p: chart["planets"][p]["sign_idx"] for p in chart["planets"]}
    g1, g2 = st.columns(2)
    with g1:
        draw_chart(style, "D1 Rasi", chart["planets"], d1, chart["lagna_idx"],
                   detail=True, transits=chart["transits"])
        st.write("")
        draw_chart(style, "D3 Drekkana", chart["planets"], chart["d3"], chart["d3_lagna"])
    with g2:
        draw_chart(style, "D9 Navamsa", chart["planets"], chart["d9"], chart["d9_lagna"])
        st.write("")
        draw_chart(style, "D10 Dasamsha", chart["planets"], chart["d10"], chart["d10_lagna"])

# ── Tab 3 ─────────────────────────────────────────────────────────────────────
with tabs[2]:
    akv = chart["ashtakavarga"]; lagna = chart["lagna_idx"]
    col = lambda v, s=False: ("var(--good)" if v >= (30 if s else 6)
                              else "var(--warn)" if v >= (26 if s else 4) else "var(--bad)")
    hdr = "".join(f"<th>{s}</th>" for s in SIGN_ABR)
    html = f"<table class='akv'><tr><th></th>{hdr}<th>Σ</th></tr>"
    for p in _AKV_PLANETS:
        row = akv[p]; nat = chart["planets"][p]["sign_idx"]; cells = ""
        for s in range(12):
            b = "font-weight:800;text-decoration:underline;" if s == nat else ""
            cells += f"<td style='color:{col(row[s])};{b}'>{row[s]}</td>"
        html += f"<tr><th style='text-align:left'>{p}</th>{cells}<td><b>{sum(row)}</b></td></tr>"
    sarva = akv["Sarva"]
    html += "<tr><th style='text-align:left'>SARVA</th>" + \
            "".join(f"<td style='color:{col(v,True)};font-weight:700'>{v}</td>" for v in sarva) + \
            f"<td><b>{sum(sarva)}</b></td></tr></table>"
    st.subheader("Bhinna + Sarvashtakavarga")
    st.markdown(html, unsafe_allow_html=True)
    st.caption("Green strong · amber average · red weak. Underlined = planet's own natal sign. "
               "Sarva: ≥30 strong, 26–29 average, ≤25 weak.")
    st.subheader(f"Transit strength ({chart['transit_date']})")
    tr = chart["transits"]
    st.dataframe([{"Planet": p, "Natal sign": SIGNS[chart["planets"][p]["sign_idx"]],
                   "Transit sign": SIGNS[tr.get(p, {}).get("sign_idx", 0)],
                   "House": (tr.get(p, {}).get("sign_idx", 0) - lagna) % 12 + 1,
                   "Bindus": akv[p][tr.get(p, {}).get("sign_idx", 0)],
                   "Strength": ("■ strong" if akv[p][tr.get(p, {}).get("sign_idx", 0)] >= 5
                                else "□ average" if akv[p][tr.get(p, {}).get("sign_idx", 0)] >= 4
                                else "✗ weak")}
                  for p in _AKV_PLANETS], hide_index=True, use_container_width=True)

# ── Tab 4 ─────────────────────────────────────────────────────────────────────
with tabs[3]:
    vp = chart["varshaphala"]
    x, y, z = st.columns(3)
    x.metric(f"Year {vp['year_number']}", f"{vp['target_year']}–{vp['target_year']+1}")
    y.metric("Annual Lagna", f"{vp['lagna']} {vp['lagna_pos']}")
    z.metric("Varsha Pati (Year Lord)", vp["varsha_pati"])
    st.markdown(f"<div class='meta'>Solar return : {vp['return_dt_utc']} · "
                f"Muntha : <b>{vp['muntha_sign']}</b> (lord {vp['muntha_lord']}) · "
                f"Weekday {vp['weekday_lord']} / Hora {vp['hora_lord']} / "
                f"Lagna lord {vp['lagna_lord']}</div>", unsafe_allow_html=True)
    st.write("")
    cc1, cc2 = st.columns([3, 2])
    with cc1:
        sr = {p: vp["planets"][p]["sign_idx"] for p in vp["planets"]}
        draw_chart(style, "Varshaphala", vp["planets"], sr, vp["lagna_si"], detail=True)
    with cc2:
        st.dataframe([{"Planet": nm, "Sign": p["sign"], "Pos": p["pos"],
                       "H": (p["sign_idx"] - vp["lagna_si"]) % 12 + 1, "Dignity": p["dignity"],
                       "↔natal": "✓" if p["sign_idx"] == chart["planets"][nm]["sign_idx"] else ""}
                      for nm in PLANET_ORDER for p in [vp["planets"][nm]] if p],
                     hide_index=True, use_container_width=True)
    mb = vp["ashtakavarga"]["Sarva"][vp["muntha_si"]]
    bad = ("b-good", "strong") if mb >= 30 else ("b-warn", "average") if mb >= 26 else ("b-bad", "weak")
    st.markdown(f"Muntha (**{vp['muntha_sign']}**) annual Sarva bindus: "
                f"<span class='badge {bad[0]}'>{mb} · {bad[1]}</span>", unsafe_allow_html=True)

# ── Tab 5 ─────────────────────────────────────────────────────────────────────
with tabs[4]:
    mahas = chart["dashas"]["mahadashas"]; mo = chart["planets"]["Moon"]
    st.caption(f"Moon {mo['sign']} {mo['pos']} · {mo['nakshatra']} (lord {mo['nak_lord']})")
    if cur["maha"]:
        st.success(f"**Today:** Mahadasha **{cur['maha']}** → Antardasha **{cur['antar']}** "
                   f"→ Pratyantardasha **{cur['pratyantar']}**")
    f = lambda dt: dt.strftime("%d %b %Y")
    st.subheader("Mahadashas")
    st.dataframe([{"Planet": md["planet"], "Start": f(md["start"]), "End": f(md["end"]),
                   "Years": round(md["years"], 1), "Active": "◄" if md["active"] else ""}
                  for md in mahas], hide_index=True, use_container_width=True)
    act = next((md for md in mahas if md["active"]), None)
    if act:
        st.subheader(f"Antardashas in {act['planet']} Mahadasha")
        st.dataframe([{"Antardasha": f"{act['planet']} / {ad['planet']}",
                       "Start": f(ad["start"]), "End": f(ad["end"]),
                       "Years": round(ad["years"], 2), "Active": "◄" if ad["active"] else ""}
                      for ad in act["antardashas"]], hide_index=True, use_container_width=True)
        aad = next((ad for ad in act["antardashas"] if ad["active"]), None)
        if aad:
            st.subheader(f"Pratyantardashas in {act['planet']} / {aad['planet']}")
            st.dataframe([{"Pratyantardasha": f"{act['planet']} / {aad['planet']} / {pad['planet']}",
                           "Start": f(pad["start"]), "End": f(pad["end"]),
                           "Years": round(pad["years"], 3), "Active": "◄" if pad["active"] else ""}
                          for pad in aad["pratyantardashas"]], hide_index=True, use_container_width=True)

# ── Tab 6: Jaimini ────────────────────────────────────────────────────────────
with tabs[5]:
    j = chart["jaimini"]
    st.caption("Chara Karakas — 8-karaka scheme. Grahas ranked by degrees traversed in "
               "their sign; **Rahu reckoned in reverse** (30° − degree). AK = highest degree.")
    jc1, jc2, jc3, jc4 = st.columns(4)
    jc1.metric("Atmakaraka (soul)", j["atmakaraka"])
    jc2.metric("Darakaraka (spouse)", j["darakaraka"])
    jc3.metric("Karakamsha", f"{j['karakamsha']}")
    jc4.metric("Arudha Lagna", f"{j['arudha_lagna']}")
    st.dataframe(
        [{"Karaka": f"{E.CHARA_ABR[r]} · {r}", "Significes": E.CHARA_MEANING[r],
          "Planet": j["karakas"][r]["planet"], "Sign": j["karakas"][r]["sign"],
          "Deg in sign": f"{j['karakas'][r]['deg_in_sign']:.2f}°",
          "Used for ranking": (f"{j['karakas'][r]['effective']:.2f}° (reverse)"
                               if j["karakas"][r]["reverse"]
                               else f"{j['karakas'][r]['effective']:.2f}°")}
         for r in j["order"]],
        hide_index=True, use_container_width=True)
    st.markdown(
        f"<div class='meta'>Karakamsha = Atmakaraka ({j['atmakaraka']}) in Navamsa → "
        f"<b>{j['karakamsha']}</b> (lord {j['karakamsha_lord']})<br>"
        f"Arudha Lagna = <b>{j['arudha_lagna']}</b> (lord {j['arudha_lagna_lord']}) · "
        f"Lagna lord {j['lagna_lord']}</div>", unsafe_allow_html=True)
    st.write("")
    st.caption("Navamsa (D9) — Karakamsha is the highlighted sign of the Atmakaraka.")
    draw_chart(style, "D9 Navamsa", chart["planets"], chart["d9"], chart["d9_lagna"])

    st.divider()
    cd = chart["chara_dasha"]
    st.subheader("Chara Dasha (Jaimini sign-based)")
    st.caption(f"Starts at the Lagna sign at birth · direction: **{cd['direction']}** "
               "(forward for odd Lagna, reverse for even). Sign duration = (count to its "
               "lord) − 1 year.")
    if cd.get("colords"):
        notes = " · ".join(f"**{sn}** → {v['lord']} ({v['reason']})"
                           for sn, v in cd["colords"].items())
        st.caption(f"Dual-lord signs resolved by Chara Bala (Jaimini strength): {notes}")
    act = next((m for m in cd["mahadashas"] if m["active"]), None)
    if act:
        aad = next((a for a in act["antardashas"] if a["active"]), None)
        st.success(f"**Today:** Chara Mahadasha **{cd['current']}**"
                   + (f" → Antardasha **{aad['sign']}**" if aad else ""))
    fd = lambda dt: dt.strftime("%d %b %Y")
    st.dataframe([{"Rasi": m["sign"], "Start": fd(m["start"]), "End": fd(m["end"]),
                   "Years": m["years"], "Active": "◄" if m["active"] else ""}
                  for m in cd["mahadashas"][:12]], hide_index=True, use_container_width=True)
    if act:
        st.markdown(f"**Antardashas in {act['sign']} Mahadasha**")
        st.dataframe([{"Antardasha": f"{act['sign']} / {a['sign']}",
                       "Start": fd(a["start"]), "End": fd(a["end"]),
                       "Years": a["years"], "Active": "◄" if a["active"] else ""}
                      for a in act["antardashas"]], hide_index=True, use_container_width=True)

st.divider()
st.caption("For study and reflection. Matches Prokerala / astro.com when pyswisseph or "
           "JPL Horizons is available; otherwise ~0.5° built-in fallback.")
