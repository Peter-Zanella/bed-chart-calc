#!/usr/bin/env python3
# Vedic Astrology (Jyotisha) Birth Chart - single-file Streamlit app.
# Charts, PDF export and chart storage are inlined here; astro_engine.py holds
# the calculations. Run: streamlit run streamlit_app.py

from datetime import date, datetime, time as dtime, timezone, timedelta
from io import BytesIO
import json, os

import streamlit as st

import astro_engine as E
from astro_engine import (SIGNS, SIGN_LORDS, PLANET_ORDER, _AKV_PLANETS,
                          SIGN_ABR, PLANET_ABR, NAKSHATRAS, NAK_ABR, _SIGN_CELL,
                          CHARA_ABR, CHARA_MEANING)


# ========== inlined: chart storage ==========
SAVE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saved_charts.json")


def load_all() -> dict:
    try:
        with open(SAVE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _write(data: dict) -> bool:
    try:
        with open(SAVE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except OSError:
        return False


def save_chart_entry(key: str, params: dict) -> bool:
    """params keys: name, gender, date(YYYY-MM-DD), time(HH:MM), lat, lon, tz, label."""
    data = load_all()
    data[key] = {**params, "_saved": datetime.now().isoformat(timespec="seconds")}
    return _write(data)


def delete_chart_entry(key: str) -> bool:
    data = load_all()
    if key in data:
        del data[key]
        return _write(data)
    return False


def to_form_defaults(entry: dict) -> dict:
    """Convert a stored entry back into widget-ready python objects."""
    y, m, d = map(int, entry["date"].split("-"))
    hh, mm = map(int, entry["time"].split(":"))
    return {
        "name": entry.get("name", ""),
        "gender": entry.get("gender", ""),
        "date": date(y, m, d),
        "time": dtime(hh, mm),
        "city": entry.get("label", ""),
        "lat": float(entry["lat"]),
        "lon": float(entry["lon"]),
        "tz": float(entry["tz"]),
        "label": entry.get("label", ""),
        "mode": "Enter coordinates",  # coords are known, so go straight to manual
    }


# ========== inlined: chart renderers ==========
# colors (kept explicit so inline SVG/HTML render the same regardless of theme)
_INK, _ACCENT, _LINE, _GOLD, _MUTE = "#2b2118", "#7b2d26", "#c9b896", "#9a7b2e", "#8a7a5c"
_LAGNA_BG = "#fdf3df"


def _nak_idx(name: str) -> int:
    return next((i for i, (n, _) in enumerate(NAKSHATRAS) if n == name), 0)


# ──────────────────────────────────────────────────────────────────────────────
# SOUTH INDIAN — fixed signs, 4x4 grid, center merged
# ──────────────────────────────────────────────────────────────────────────────
def south_indian_html(title, planet_data, placements, lagna_si,
                      detail=False, transits=None) -> str:
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
            na = NAK_ABR[_nak_idx(pd.get("nakshatra", ""))]
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

    grid = {pos: si for si, pos in _SIGN_CELL.items()}
    rows = [
        "<tr>" + "".join(cell(grid[(0, c)]) for c in range(4)) + "</tr>",
        f"<tr>{cell(grid[(1,0)])}"
        f"<td class='center' colspan='2' rowspan='2'>{title}</td>"
        f"{cell(grid[(1,3)])}</tr>",
        f"<tr>{cell(grid[(2,0)])}{cell(grid[(2,3)])}</tr>",
        "<tr>" + "".join(cell(grid[(3, c)]) for c in range(4)) + "</tr>",
    ]
    return f"<div class='si-wrap'><table class='si'>{''.join(rows)}</table></div>"


# ──────────────────────────────────────────────────────────────────────────────
# NORTH INDIAN — fixed houses (diamond), signs rotate, Lagna at top-center
# ──────────────────────────────────────────────────────────────────────────────
# centroid of each house region within a 10..310 square
_HC = {1:(160,82),2:(82,40),3:(40,82),4:(82,160),5:(40,238),6:(82,280),
       7:(160,240),8:(238,280),9:(280,238),10:(240,160),11:(280,82),12:(238,40)}
# house-1 polygon (for the faint Lagna fill)
_H1_POLY = "160,10 235,85 160,160 85,85"


def north_indian_svg(title, planet_data, placements, lagna_si, detail=False) -> str:
    by_house = {h: [] for h in range(1, 13)}
    for p, si in placements.items():
        if p == "Ascendant":
            continue
        by_house[(si - lagna_si) % 12 + 1].append(p)

    parts = [
        f"<svg viewBox='0 0 320 350' xmlns='http://www.w3.org/2000/svg' "
        f"style='width:100%;max-width:360px;font-family:DejaVu Sans Mono,monospace'>",
        f"<text x='160' y='338' text-anchor='middle' font-size='14' "
        f"fill='{_ACCENT}' font-weight='bold' font-family='Georgia,serif'>{title}</text>",
        f"<polygon points='{_H1_POLY}' fill='{_LAGNA_BG}'/>",
    ]
    L = f"stroke='{_LINE}' stroke-width='1.4'"
    # outer square, diagonals, inner diamond
    parts.append(f"<rect x='10' y='10' width='300' height='300' fill='none' {L}/>")
    parts.append(f"<line x1='10' y1='10' x2='310' y2='310' {L}/>")
    parts.append(f"<line x1='310' y1='10' x2='10' y2='310' {L}/>")
    parts.append(f"<polygon points='160,10 310,160 160,310 10,160' fill='none' {L}/>")

    for h in range(1, 13):
        sign = (lagna_si + h - 1) % 12
        cx, cy = _HC[h]
        pls = by_house[h]
        n = len(pls)
        sign_y = cy - (n * 6) - 4
        parts.append(
            f"<text x='{cx}' y='{sign_y}' text-anchor='middle' font-size='9' "
            f"fill='{_MUTE}'>{SIGN_ABR[sign]}{' ⬩La' if h==1 else ''}</text>"
        )
        if n:
            start = cy - (n - 1) * 6 + 4
            spans = ""
            for i, p in enumerate(pls):
                ab = PLANET_ABR.get(p, p[:2])
                deg = ""
                if detail:
                    pd = planet_data.get(p, {})
                    if pd:
                        deg = f" {int(pd['lon']%30)}°"
                spans += (f"<tspan x='{cx}' dy='{0 if i==0 else 12}'>{ab}{deg}</tspan>")
            parts.append(
                f"<text x='{cx}' y='{start}' text-anchor='middle' font-size='11' "
                f"fill='{_INK}' font-weight='600'>{spans}</text>"
            )
    parts.append("</svg>")
    return "".join(parts)


# ──────────────────────────────────────────────────────────────────────────────
# BHAVA CHALIT — South-Indian box (Pisces top-left). Planets placed by their
# bhava (Ascendant = bhava madhya); a planet shifted from its rasi house shows
# its rasi sign in brackets. Degrees/nakshatra stay in the D1 Rasi.
# ──────────────────────────────────────────────────────────────────────────────
def bhava_grid_html(place, planet_data, lagna_si) -> str:
    natal = {i: [] for i in range(12)}
    for p, si in place.items():
        natal[si].append(p)
    grid = {rc: si for si, rc in _SIGN_CELL.items()}

    def cell(r, c):
        si = grid[(r, c)]
        house = (si - lagna_si) % 12 + 1
        is_l = (si == lagna_si)
        hdr = f"{'◆ ' if is_l else ''}{SIGN_ABR[si]} · H{house}"
        items = []
        for p in natal[si]:
            pd = planet_data.get(p, {})
            shifted = pd.get("sign_idx") != si
            extra = (f" <span class='bh-deg'>(in {SIGN_ABR[pd['sign_idx']]})</span>"
                     if shifted else "")
            items.append(f"<span class='si-natal'>{PLANET_ABR.get(p, p[:2])}"
                         f"{extra}</span>")
        return (f"<td class='{'lagna' if is_l else ''}'>"
                f"<span class='si-hdr'>{hdr}</span>{'<br>'.join(items)}</td>")

    rows = [
        "<tr>" + "".join(cell(0, c) for c in range(4)) + "</tr>",
        f"<tr>{cell(1,0)}"
        f"<td class='center' colspan='2' rowspan='2'>Bhava<br>Chalit</td>"
        f"{cell(1,3)}</tr>",
        f"<tr>{cell(2,0)}{cell(2,3)}</tr>",
        "<tr>" + "".join(cell(3, c) for c in range(4)) + "</tr>",
    ]
    return f"<div class='si-wrap'><table class='si'>{''.join(rows)}</table></div>"


# ========== inlined: PDF report ==========
_P_INK = "#2b2118"; _P_ACCENT = "#7b2d26"; _P_LINE = "#d9c9a8"; _P_PAPER = "#fbf7ef"
_P_GOOD = "#2e7d4f"; _P_WARN = "#b07d18"; _P_BAD = "#9a342c"; _P_LAGNA = "#fdf3df"

# Bhava chart cell map: signs fixed with Pisces (11) top-right, zodiac clockwise
_BHAVA_CELL = {0: (1, 3), 1: (2, 3), 2: (3, 3), 3: (3, 2), 4: (3, 1), 5: (3, 0),
               6: (2, 0), 7: (1, 0), 8: (0, 0), 9: (0, 1), 10: (0, 2), 11: (0, 3)}


def _have_reportlab() -> bool:
    try:
        import reportlab  # noqa: F401
        return True
    except ImportError:
        return False


def build_pdf(chart: dict) -> bytes:
    if not _have_reportlab():
        raise RuntimeError("reportlab not installed")

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether,
    )

    ink = colors.HexColor(_P_INK); accent = colors.HexColor(_P_ACCENT)
    line = colors.HexColor(_P_LINE); paper = colors.HexColor(_P_PAPER)
    lagna_bg = colors.HexColor(_P_LAGNA)
    cmap = {"good": colors.HexColor(_P_GOOD), "warn": colors.HexColor(_P_WARN),
            "bad": colors.HexColor(_P_BAD)}

    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Title"], textColor=accent, fontName="Times-Bold",
                        fontSize=20, spaceAfter=2, alignment=1)
    sub = ParagraphStyle("sub", parent=ss["Normal"], textColor=ink, fontSize=9,
                         alignment=1, spaceAfter=10)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], textColor=accent,
                        fontName="Times-Bold", fontSize=13, spaceBefore=10, spaceAfter=4)
    body = ParagraphStyle("body", parent=ss["Normal"], textColor=ink, fontSize=9, leading=13)
    small = ParagraphStyle("small", parent=ss["Normal"], textColor=ink, fontSize=7.5, leading=9)
    cap = ParagraphStyle("cap", parent=ss["Normal"], textColor=colors.HexColor("#7a6a4c"),
                         fontSize=7.5, leading=10)

    m = chart["meta"]
    story = []

    story.append(Paragraph("✦ Vedic Astrology Birth Chart ✦", h1))
    story.append(Paragraph("Jyotisha · Lahiri Ayanamsha · Whole-Sign Houses", sub))

    g = f" ({m['gender']})" if m.get("gender") else ""
    meta_rows = [
        ["Name", f"{m.get('name') or '—'}{g}"],
        ["Birth", f"{m['birth']}  ({m['tz']})"],
        ["UT", m["ut"]],
        ["Location", f"{m['location'] or '—'}  ·  {m['lat']:.4f}° N / {m['lon']:.4f}° E"],
        ["Lagna", f"{chart['lagna']} {chart['lagna_pos']}"],
        ["Julian Day / Ayanamsha", f"{m['jd']}  /  {m['ayan']}° (Lahiri)"],
        ["Engine", m["engine"]],
    ]
    mt = Table(meta_rows, colWidths=[42 * mm, 130 * mm])
    mt.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Times-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("TEXTCOLOR", (0, 0), (-1, -1), ink),
        ("LINEBELOW", (0, 0), (-1, -2), 0.3, line),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(mt)

    pa = chart.get("panchang")
    if pa:
        story.append(Paragraph(
            f"<b>Panchanga:</b> Tithi {pa['tithi']} (lunar day {pa['tithi_num']}/30) · "
            f"Vara {pa['vara']} (lord {pa['vara_lord']}) · Nakshatra {pa['nakshatra']} "
            f"(lord {pa['nakshatra_lord']}) · Yoga {pa['yoga']} · Karana {pa['karana']}.", body))

    # ── planets ───────────────────────────────────────────────────────────────
    story.append(Paragraph("Graha (Planets)", h2))
    head = ["Planet", "Sign", "Pos", "H", "Nakshatra", "Pada", "Lord", "Dignity"]
    data = [head]
    for nm in PLANET_ORDER:
        p = chart["planets"][nm]
        data.append([nm, p["sign"], p["pos"], str(p.get("house", "—")),
                     p["nakshatra"], str(p["pada"]), p["nak_lord"], p["dignity"]])
    pt = Table(data, repeatRows=1, colWidths=[20*mm,18*mm,16*mm,8*mm,26*mm,11*mm,18*mm,28*mm])
    pt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), paper),
        ("FONTNAME", (0, 0), (-1, 0), "Times-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8), ("TEXTCOLOR", (0, 0), (-1, -1), ink),
        ("GRID", (0, 0), (-1, -1), 0.3, line),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f1e4")]),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]))
    story.append(pt)

    # ── houses ────────────────────────────────────────────────────────────────
    story.append(Paragraph("Bhava (Houses)", h2))
    hdata = [["H", "Sign", "Lord", "Occupants"]]
    for h in range(1, 13):
        sn = chart["houses"][h]
        hdata.append([str(h), sn, SIGN_LORDS[sn], ", ".join(chart["occupants"][h]) or "—"])
    ht = Table(hdata, repeatRows=1, colWidths=[10*mm, 22*mm, 22*mm, 118*mm])
    ht.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), paper),
        ("FONTNAME", (0, 0), (-1, 0), "Times-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8), ("TEXTCOLOR", (0, 0), (-1, -1), ink),
        ("GRID", (0, 0), (-1, -1), 0.3, line),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]))
    story.append(ht)

    # ── South Indian D1 + D9 as tables ──────────────────────────────────────────
    def si_table(title, placements, lagna_si, cellmap=_SIGN_CELL):
        natal = {i: [] for i in range(12)}
        for p, si in placements.items():
            if p != "Ascendant":
                natal[si].append(PLANET_ABR.get(p, p[:2]))
        grid_sign = {pos: si for si, pos in cellmap.items()}
        data = [[None] * 4 for _ in range(4)]
        spans = []
        for (r, c), si in grid_sign.items():
            house = (si - lagna_si) % 12 + 1
            tag = "◆" if si == lagna_si else ""
            txt = f"<b>{SIGN_ABR[si]}{tag} H{house}</b>"
            if natal[si]:
                txt += "<br/>" + " ".join(natal[si])
            data[r][c] = Paragraph(txt, small)
        data[1][1] = Paragraph(f"<b>{title}</b>", ParagraphStyle(
            "ctr", parent=small, alignment=1, textColor=accent, fontName="Times-Bold", fontSize=9))
        data[1][2] = ""; data[2][1] = ""; data[2][2] = ""
        spans.append(("SPAN", (1, 1), (2, 2)))
        t = Table(data, colWidths=[22 * mm] * 4, rowHeights=[18 * mm] * 4)
        styl = [("GRID", (0, 0), (-1, -1), 0.4, line),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (1, 1), (2, 2), paper)]
        for (r, c), si in grid_sign.items():
            if si == lagna_si:
                styl.append(("BACKGROUND", (c, r), (c, r), lagna_bg))
        t.setStyle(TableStyle(styl + spans))
        return t

    story.append(Paragraph("Divisional Charts (South Indian)", h2))
    d1_pl = {p: chart["planets"][p]["sign_idx"] for p in chart["planets"]}
    crow = lambda a, b: Table([[a, b]], colWidths=[90 * mm, 90 * mm], style=TableStyle(
        [("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    story.append(KeepTogether(crow(
        si_table("D1 Rasi", d1_pl, chart["lagna_idx"]),
        si_table("D9 Navamsa", chart["d9"], chart["d9_lagna"]))))
    story.append(Spacer(1, 3 * mm))
    story.append(KeepTogether(crow(
        si_table("D3 Drekkana", chart["d3"], chart["d3_lagna"]),
        si_table("D10 Dasamsha", chart["d10"], chart["d10_lagna"]))))

    # ── bhava chalit chart + transit charts ─────────────────────────────────────
    tr = chart.get("transits", {})
    trans_pl = {p: tr[p]["sign_idx"] for p in tr if p != "Ascendant"} if tr else {}
    bhava_pl = chart.get("bhava", {}).get("place") or d1_pl   # fallback to rasi if absent
    t_lagna  = chart.get("transit_lagna_idx", chart["lagna_idx"])
    story.append(Paragraph("Bhava Chalit &amp; Transit Charts (South Indian)", h2))
    story.append(KeepTogether(crow(
        si_table("Bhava Chalit", bhava_pl, chart["lagna_idx"]),
        si_table(f"Transits (vs natal) {chart.get('transit_date','')}",
                 trans_pl, chart["lagna_idx"]))))
    story.append(KeepTogether(crow(
        si_table(f"Now-chart · Lagna {chart.get('transit_lagna_pos','')} {SIGNS[t_lagna]}",
                 trans_pl, t_lagna),
        Spacer(1, 1))))
    story.append(Paragraph(
        "Bhava Chalit: houses centred on the Ascendant degree, so a planet near a sign edge "
        "can fall into the adjacent bhava. &nbsp; Transits (vs natal): current sky against the "
        "birth Lagna. &nbsp; Now-chart: same transiting planets, but houses counted from the "
        f"Lagna at chart-creation time ({chart.get('transit_local', chart.get('transit_date',''))} "
        "local, at the birthplace).", cap))

    # ── ashtakavarga ────────────────────────────────────────────────────────────
    story.append(Paragraph("Ashtakavarga", h2))
    akv = chart["ashtakavarga"]
    head = [""] + SIGN_ABR + ["Σ"]
    adata = [head]
    color_cells = []
    for ri, p in enumerate(_AKV_PLANETS, start=1):
        row = akv[p]
        adata.append([p] + [str(v) for v in row] + [str(sum(row))])
        for s in range(12):
            v = row[s]
            key = "good" if v >= 6 else "warn" if v >= 4 else "bad"
            color_cells.append(("TEXTCOLOR", (s + 1, ri), (s + 1, ri), cmap[key]))
    sarva = akv["Sarva"]
    adata.append(["SARVA"] + [str(v) for v in sarva] + [str(sum(sarva))])
    sr = len(adata) - 1
    for s in range(12):
        v = sarva[s]
        key = "good" if v >= 30 else "warn" if v >= 26 else "bad"
        color_cells.append(("TEXTCOLOR", (s + 1, sr), (s + 1, sr), cmap[key]))
    at = Table(adata, repeatRows=1,
               colWidths=[16 * mm] + [12 * mm] * 12 + [12 * mm])
    at.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), paper),
        ("FONTNAME", (0, 0), (-1, 0), "Times-Bold"),
        ("FONTNAME", (0, -1), (0, -1), "Times-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5), ("TEXTCOLOR", (0, 0), (0, -1), ink),
        ("GRID", (0, 0), (-1, -1), 0.3, line),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ] + color_cells))
    story.append(at)
    story.append(Paragraph("Bhinna per planet + Sarva. Green strong · amber average · red weak. "
                           "Sarva: ≥30 strong, 26–29 average, ≤25 weak.", cap))

    # ── varshaphala ─────────────────────────────────────────────────────────────
    vp = chart.get("varshaphala")
    if vp:
        story.append(Paragraph("Varshaphala (Solar Return)", h2))
        story.append(Paragraph(
            f"Year {vp['year_number']} ({vp['target_year']}–{vp['target_year']+1}) · "
            f"Annual Lagna <b>{vp['lagna']} {vp['lagna_pos']}</b> · "
            f"Muntha <b>{vp['muntha_sign']}</b> (lord {vp['muntha_lord']}) · "
            f"Varsha Pati <b>{vp['varsha_pati']}</b> · Solar return {vp['return_dt_utc']}", body))
        vp_pl = {p: vp["planets"][p]["sign_idx"] for p in vp["planets"]}
        story.append(KeepTogether(crow(
            si_table("Varshaphala (annual)", vp_pl, vp["lagna_si"]),
            Paragraph("Annual (solar-return) chart cast for the Sun's return to its natal "
                      "sidereal longitude. ◆ marks the annual Lagna.", cap))))

    # ── dasha ───────────────────────────────────────────────────────────────────
    story.append(Paragraph("Vimshottari Dasha", h2))
    cur = chart["dashas"]["current"]
    if cur["maha"]:
        story.append(Paragraph(
            f"<b>Today:</b> Mahadasha {cur['maha']} -&gt; Antardasha {cur['antar']} "
            f"-&gt; Pratyantardasha {cur['pratyantar']}", body))
    fmt = lambda dt: dt.strftime("%d %b %Y")
    ddata = [["Mahadasha", "Start", "End", "Years"]]
    for md in chart["dashas"]["mahadashas"]:
        mk = "  (now)" if md["active"] else ""
        ddata.append([md["planet"] + mk, fmt(md["start"]), fmt(md["end"]), f"{md['years']:.1f}"])
    dt_tbl = Table(ddata, repeatRows=1, colWidths=[40*mm, 35*mm, 35*mm, 20*mm])
    dt_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), paper),
        ("FONTNAME", (0, 0), (-1, 0), "Times-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8), ("TEXTCOLOR", (0, 0), (-1, -1), ink),
        ("GRID", (0, 0), (-1, -1), 0.3, line),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]))
    story.append(dt_tbl)

    # active antardashas
    act = next((md for md in chart["dashas"]["mahadashas"] if md["active"]), None)
    if act:
        story.append(Paragraph(f"Antardashas in {act['planet']} Mahadasha", h2))
        adata = [["Antardasha", "Start", "End", "Years"]]
        for ad in act["antardashas"]:
            mk = "  (now)" if ad["active"] else ""
            adata.append([f"{act['planet']} / {ad['planet']}{mk}",
                          fmt(ad["start"]), fmt(ad["end"]), f"{ad['years']:.2f}"])
        adt = Table(adata, repeatRows=1, colWidths=[50*mm, 35*mm, 35*mm, 20*mm])
        adt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), paper), ("FONTNAME", (0, 0), (-1, 0), "Times-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8), ("TEXTCOLOR", (0, 0), (-1, -1), ink),
            ("GRID", (0, 0), (-1, -1), 0.3, line),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]))
        story.append(adt)

    # ── transit strength ────────────────────────────────────────────────────────
    tr = chart.get("transits", {})
    if tr:
        story.append(Paragraph(f"Transit Strength ({chart['transit_date']})", h2))
        tdata = [["Planet", "Natal", "Transit", "H", "Bindus", "Strength"]]
        for p in _AKV_PLANETS:
            nat = chart["planets"][p]["sign_idx"]; tsi = tr.get(p, {}).get("sign_idx", nat)
            b = chart["ashtakavarga"][p][tsi]
            s = "strong" if b >= 5 else "average" if b >= 4 else "weak"
            tdata.append([p, SIGNS[nat], SIGNS[tsi], str((tsi - chart["lagna_idx"]) % 12 + 1),
                          str(b), s])
        tt = Table(tdata, repeatRows=1, colWidths=[24*mm, 28*mm, 28*mm, 10*mm, 16*mm, 24*mm])
        tt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), paper), ("FONTNAME", (0, 0), (-1, 0), "Times-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8), ("TEXTCOLOR", (0, 0), (-1, -1), ink),
            ("GRID", (0, 0), (-1, -1), 0.3, line),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]))
        story.append(tt)

    # ── jaimini ─────────────────────────────────────────────────────────────────
    j = chart.get("jaimini")
    if j:
        story.append(Paragraph("Jaimini — Chara Karakas (8-karaka, incl. Rahu)", h2))
        story.append(Paragraph(
            f"Atmakaraka <b>{j['atmakaraka']}</b> · Darakaraka <b>{j['darakaraka']}</b> · "
            f"Karakamsha <b>{j['karakamsha']}</b> (lord {j['karakamsha_lord']}) · "
            f"Arudha Lagna <b>{j['arudha_lagna']}</b> (lord {j['arudha_lagna_lord']}) · "
            f"Upapada Lagna <b>{j['upapada_lagna']}</b> (lord {j['upapada_lagna_lord']}). "
            f"Rahu is reckoned in reverse (30 deg minus its degree).", body))
        jdata = [["Karaka", "Significes", "Planet", "Sign", "Deg in sign", "Ranking deg"]]
        for r in j["order"]:
            k = j["karakas"][r]
            jdata.append([f"{CHARA_ABR[r]} {r}", CHARA_MEANING[r], k["planet"], k["sign"],
                          f"{k['deg_in_sign']:.2f}",
                          f"{k['effective']:.2f}{' (rev)' if k['reverse'] else ''}"])
        jt = Table(jdata, repeatRows=1,
                   colWidths=[34*mm, 34*mm, 20*mm, 22*mm, 24*mm, 26*mm])
        jt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), paper), ("FONTNAME", (0, 0), (-1, 0), "Times-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5), ("TEXTCOLOR", (0, 0), (-1, -1), ink),
            ("GRID", (0, 0), (-1, -1), 0.3, line),
            ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#fdf3df")),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]))
        story.append(jt)

    # ── chara dasha ─────────────────────────────────────────────────────────────
    cd = chart.get("chara_dasha")
    if cd:
        story.append(Paragraph("Jaimini — Chara Dasha", h2))
        note = (f"Sign-based dasha from the Lagna at birth; direction: <b>{cd['direction']}</b>. "
                f"Duration = (count to lord) minus 1 year.")
        if cd.get("colords"):
            note += " Dual-lord signs resolved by Chara Bala (Jaimini strength): " + \
                    "; ".join(f"{sn} -&gt; {v['lord']} ({v['reason']})"
                              for sn, v in cd["colords"].items()) + "."
        story.append(Paragraph(note, body))
        cddata = [["Rasi", "Start", "End", "Years"]]
        for m in cd["mahadashas"][:12]:
            mk = "  (now)" if m["active"] else ""
            cddata.append([m["sign"] + mk, fmt(m["start"]), fmt(m["end"]), str(m["years"])])
        cdt = Table(cddata, repeatRows=1, colWidths=[40*mm, 35*mm, 35*mm, 20*mm])
        cdt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), paper), ("FONTNAME", (0, 0), (-1, 0), "Times-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8), ("TEXTCOLOR", (0, 0), (-1, -1), ink),
            ("GRID", (0, 0), (-1, -1), 0.3, line),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]))
        story.append(cdt)
        # antardashas of the active Chara mahadasha
        cact = next((m for m in cd["mahadashas"][:12] if m["active"]), None)
        if cact:
            story.append(Paragraph(f"Antardashas in {cact['sign']} (current Chara Mahadasha)", h2))
            cadata = [["Antardasha", "Start", "End", "Years"]]
            for a in cact["antardashas"]:
                mk = "  (now)" if a["active"] else ""
                cadata.append([f"{cact['sign']} / {a['sign']}{mk}",
                               fmt(a["start"]), fmt(a["end"]), str(a["years"])])
            cat = Table(cadata, repeatRows=1, colWidths=[40*mm, 35*mm, 35*mm, 20*mm])
            cat.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), paper), ("FONTNAME", (0, 0), (-1, 0), "Times-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8), ("TEXTCOLOR", (0, 0), (-1, -1), ink),
                ("GRID", (0, 0), (-1, -1), 0.3, line),
                ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]))
            story.append(cat)

    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("Generated by the Vedic Astrology Streamlit app · for study and reflection.", cap))

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=14*mm, rightMargin=14*mm,
                            topMargin=12*mm, bottomMargin=12*mm,
                            title="Vedic Birth Chart")
    doc.build(story)
    return buf.getvalue()


# ========== application UI ==========
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
  .bh-wrap { overflow-x:auto; }
  table.bh { border-collapse:collapse; width:100%; font-family:'DejaVu Sans Mono',monospace; }
  table.bh td {
    border:1px solid var(--line); width:25%; vertical-align:top; padding:6px 8px;
    background:#fff; font-size:12px; line-height:1.4;
  }
  table.bh td.bh-l { background:#fdf3df; box-shadow: inset 0 0 0 2px var(--gold); }
  .bh-hdr { color:var(--accent); font-weight:700; font-size:12px; }
  .bh-sign { color:#8a7a5c; font-size:10px; margin-bottom:3px; }
  .bh-p { color:var(--ink); font-weight:600; }
  .bh-deg { color:#8a7a5c; font-weight:400; font-size:10px; }
  .bh-empty { color:#c9b896; }
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
    return build_pdf(compute(params))

@st.cache_data(show_spinner=False, ttl=86400)
def resolve_city(city: str, y: int, mo: int, d: int, h: int, mi: int):
    # cached across sessions so the same place isn't geocoded repeatedly
    return E.resolve_location(city, y, mo, d, h, mi)


@st.cache_data(show_spinner=False)
def muhurta(activity: str, lat: float, lon: float, tz: float, start_iso: str, days: int):
    return E.compute_muhurta(activity, lat, lon, tz, date.fromisoformat(start_iso), days)


def draw_chart(style, label, planet_data, placements, lagna_si, detail=False, transits=None):
    if style == "North Indian":
        st.markdown(
            north_indian_svg(label, planet_data, placements, lagna_si, detail),
            unsafe_allow_html=True)
    else:
        st.markdown(
            south_indian_html(label, planet_data, placements, lagna_si, detail, transits),
            unsafe_allow_html=True)


def _parse_time(s, fallback):
    """Lenient HH:MM (24h) parser — also accepts '1355', '9.5'→no, '13.55', '13h55'."""
    s = (s or "").strip().lower().replace(".", ":").replace("h", ":").replace(" ", "")
    try:
        if ":" in s:
            hh, mm = (s.split(":") + ["0"])[:2]
        elif s.isdigit() and len(s) in (3, 4):
            hh, mm = s[:-2], s[-2:]
        elif s.isdigit():
            hh, mm = s, "0"
        else:
            return None
        h, m = int(hh), int(mm or 0)
        if 0 <= h <= 23 and 0 <= m <= 59:
            return dtime(h, m)
    except Exception:
        pass
    return None


# ──────────────────────────────────────────────────────────────────────────────
# FORM DEFAULTS  (a nonce in the widget keys lets "Load" reset the inputs cleanly)
# ──────────────────────────────────────────────────────────────────────────────
DEFAULTS = {"name": "", "gender": "", "date": date(1957, 8, 24), "time": dtime(13, 55),
            "city": "Liestal, Switzerland", "lat": 47.4833, "lon": 7.7356, "tz": 1.0,
            "label": "Liestal, Switzerland", "mode": "Search by city"}


def _load_from_url():
    """If the page URL carries a chart (bookmarked link), seed the inputs from it once."""
    qp = st.query_params
    if "lat" not in qp or st.session_state.get("active_params"):
        return
    try:
        d = date(int(qp["y"]), int(qp["mo"]), int(qp["d"]))
        t = dtime(int(qp["h"]), int(qp["mi"]))
        st.session_state["form_defaults"] = {
            "name": qp.get("nm", ""), "gender": qp.get("g", ""), "date": d, "time": t,
            "city": qp.get("loc", ""), "lat": float(qp["lat"]), "lon": float(qp["lon"]),
            "tz": float(qp["tz"]), "label": qp.get("loc", ""), "mode": "Enter coordinates"}
        st.session_state["active_params"] = dict(
            year=d.year, month=d.month, day=d.day, hour=t.hour, minute=t.minute,
            lat=float(qp["lat"]), lon=float(qp["lon"]), tz_offset=float(qp["tz"]),
            location=qp.get("loc", ""), name=qp.get("nm", ""), gender=qp.get("g", ""))
    except Exception:
        pass


_load_from_url()
fd = {**DEFAULTS, **st.session_state.get("form_defaults", {})}
n = st.session_state.setdefault("nonce", 0)
k = lambda name: f"{name}_{n}"   # versioned widget key


def load_entry(key, entry):
    d = to_form_defaults(entry)
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
saved = load_all()
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
            delete_chart_entry(key); st.rerun()
    st.caption("Saved charts live on the server and reset when the app sleeps. "
               "**Back up** to a file to keep them, or bookmark a chart's link (below).")
    bcol1, bcol2 = st.columns(2)
    if saved:
        bcol1.download_button("⬇ Back up", data=json.dumps(saved, indent=2, ensure_ascii=False),
                              file_name="vedic_saved_charts.json", mime="application/json",
                              use_container_width=True)
    up = bcol2.file_uploader("⬆ Restore", type="json", key="restore_charts",
                             label_visibility="collapsed")
    if up is not None and not st.session_state.get("_restored"):
        try:
            incoming = json.loads(up.getvalue().decode("utf-8"))
            for ekey, eentry in incoming.items():
                save_chart_entry(ekey, eentry)
            st.session_state["_restored"] = True
            st.success(f"Restored {len(incoming)} chart(s).")
            st.rerun()
        except Exception as e:
            st.error(f"Couldn't read that backup file ({e}).")
    if up is None:
        st.session_state.pop("_restored", None)

# ──────────────────────────────────────────────────────────────────────────────
# SIDEBAR — birth details
# ──────────────────────────────────────────────────────────────────────────────
st.sidebar.header("Birth details")
name = st.sidebar.text_input("Name", fd["name"], key=k("name"))
gender = st.sidebar.selectbox("Gender", ["", "Male", "Female"],
                              index=["", "Male", "Female"].index(fd["gender"]), key=k("gender"))
bdate = st.sidebar.date_input("Birth date", value=fd["date"],
                              min_value=date(1800, 1, 1), max_value=date(2100, 12, 31), key=k("date"))
_tstr = st.sidebar.text_input("Birth time (local · 24h HH:MM)",
                              value=fd["time"].strftime("%H:%M"), key=k("time"),
                              help="Type the time directly, e.g. 09:05 or 13:55")
btime = _parse_time(_tstr, fd["time"])
if btime is None:
    st.sidebar.error("Enter the time as HH:MM (24-hour), e.g. 13:55.")
    btime = fd["time"]

st.sidebar.divider()
mode = st.sidebar.radio("Location", ["Search by city", "Enter coordinates"],
                        index=["Search by city", "Enter coordinates"].index(fd["mode"]), key=k("mode"))

lat = lon = tz_offset = loc_label = None
if mode == "Search by city":
    city = st.sidebar.text_input("City", fd["city"], key=k("city"))
    # auto-resolve whenever city / date / time change (offset depends on the date)
    cur_q = [city.strip().lower(), bdate.year, bdate.month, bdate.day, btime.hour, btime.minute]
    geo = st.session_state.get("geo")
    if city.strip() and (not geo or geo.get("_query") != cur_q):
        with st.spinner("Resolving location…"):
            g = resolve_city(city.strip(), bdate.year, bdate.month, bdate.day,
                             btime.hour, btime.minute)
        geo = dict(g) if g else {"_notfound": True}
        geo["_query"] = cur_q
        st.session_state["geo"] = geo
    if not city.strip():
        st.sidebar.caption("Type a city — coordinates resolve automatically.")
    elif geo.get("_notfound"):
        st.sidebar.warning("City not found — check the spelling or switch to "
                           "*Enter coordinates*.")
    else:
        lat, lon, tz_offset, loc_label = geo["lat"], geo["lon"], geo["offset"], geo["label"]
        st.sidebar.success(f"{loc_label}\n\n{lat:.4f}°, {lon:.4f}°\n\n"
                           f"{geo.get('iana','?')} · {geo['offset_str']}")
        if geo.get("approx"):
            st.sidebar.caption("⚠ Timezone estimated from longitude — verify the UTC "
                               "offset, or set it exactly via *Enter coordinates*.")
else:
    lat = st.sidebar.number_input("Latitude (N+)", value=fd["lat"], format="%.4f", key=k("lat"))
    lon = st.sidebar.number_input("Longitude (E+)", value=fd["lon"], format="%.4f", key=k("lon"))
    tz_offset = st.sidebar.number_input("UTC offset (+1 CET, +5.5 IST)", value=fd["tz"],
                                        step=0.5, format="%.2f", key=k("tz"))
    loc_label = st.sidebar.text_input("Location label", fd["label"], key=k("label"))

# the chart parameters implied by the current sidebar state (None if no location yet)
pending = None
if lat is not None and lon is not None and tz_offset is not None:
    pending = dict(year=bdate.year, month=bdate.month, day=bdate.day,
                   hour=btime.hour, minute=btime.minute,
                   lat=lat, lon=lon, tz_offset=tz_offset,
                   location=loc_label or "", name=name, gender=gender)

if st.sidebar.button("✦ Generate chart", type="primary", use_container_width=True):
    if pending is None:
        st.sidebar.error("Set a location first (type a city or enter coordinates).")
    else:
        st.session_state["active_params"] = pending

# once a chart exists, keep it in sync with the sidebar automatically —
# changing the location (or any input) updates the chart with no extra click
if st.session_state.get("active_params") and pending and \
        pending != st.session_state["active_params"]:
    st.session_state["active_params"] = pending

# mirror the active chart into the page URL so it can be bookmarked / reopened
_ap = st.session_state.get("active_params")
if _ap:
    _want = {"y": str(_ap["year"]), "mo": str(_ap["month"]), "d": str(_ap["day"]),
             "h": str(_ap["hour"]), "mi": str(_ap["minute"]),
             "lat": f"{_ap['lat']:.4f}", "lon": f"{_ap['lon']:.4f}",
             "tz": f"{_ap['tz_offset']:g}", "loc": _ap["location"] or "",
             "nm": _ap["name"] or "", "g": _ap["gender"] or ""}
    if {kk: st.query_params.get(kk) for kk in _want} != _want:
        st.query_params.update(_want)


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────
st.title("✦ Vedic Astrology Birth Chart")
st.caption("Jyotiṣa · Lahiri Ayanamsha · Whole-Sign Houses")

view = st.radio("View", ["Birth chart", "Prashna (horary)"],
                horizontal=True, label_visibility="collapsed", key="app_view")

# ── Prashna — standalone (needs no birth chart) ───────────────────────────────
if view == "Prashna (horary)":
    st.subheader("Prashna — horary chart for a question")
    st.caption("Prashna casts a chart for the **moment a question is asked**, at **your current "
               "location**. No birth data needed — the left sidebar is only for birth charts. "
               "Enter where you are now, optionally your question, then cast — the chart freezes "
               "at that moment.")
    pq = st.text_input("Your question (optional — kept on screen only)", key="prashna_q",
                       placeholder="e.g. Will the journey go well?")
    pc1, pc2 = st.columns([3, 2])
    p_city = (pc1.text_input("Your current location (city)", key="prashna_city",
                             placeholder="e.g. Zürich, Switzerland") or "").strip()
    p_geo = None
    if p_city:
        _now = datetime.now()
        with st.spinner("Resolving location…"):
            p_geo = resolve_city(p_city, _now.year, _now.month, _now.day, _now.hour, _now.minute)
        if not p_geo:
            pc2.warning("Location not found — check the spelling.")
        else:
            pc2.success(f"{p_geo['label']}\n\n{p_geo['lat']:.4f}°, {p_geo['lon']:.4f}°\n\n"
                        f"{p_geo.get('iana','?')} · {p_geo['offset_str']}")
            if p_geo.get("approx"):
                pc2.caption("⚠ Timezone estimated from longitude.")
    else:
        pc2.caption("Type your current city — coordinates and time zone resolve automatically.")

    pstyle = st.radio("Chart style", ["South Indian", "North Indian"],
                      horizontal=True, key="prashna_style")

    manual = st.checkbox("Cast for a specific time (default: now)", key="prashna_manual")
    p_when = None
    if manual:
        mc1, mc2 = st.columns(2)
        m_date = mc1.date_input("Date (local at that place)", value=date.today(),
                                min_value=date(1800, 1, 1), max_value=date(2100, 12, 31),
                                key="prashna_date")
        m_tstr = mc2.text_input("Time (24h HH:MM)", value=datetime.now().strftime("%H:%M"),
                                key="prashna_time", help="Type it directly, e.g. 09:05 or 13:55")
        m_time = _parse_time(m_tstr, None)
        if m_time is None:
            mc2.error("Enter the time as HH:MM (24-hour).")
        else:
            p_when = (m_date, m_time)

    cast_ok = bool(p_geo) and (not manual or p_when is not None)
    if st.button("🔮 Cast Prashna" + ("" if manual else " for this moment"),
                 type="primary", disabled=not cast_ok):
        if manual and p_when:
            md, mt = p_when
            local = datetime(md.year, md.month, md.day, mt.hour, mt.minute,
                             tzinfo=timezone(timedelta(hours=p_geo["offset"])))
        else:
            local = datetime.now(timezone.utc).astimezone(
                timezone(timedelta(hours=p_geo["offset"])))
        st.session_state["prashna"] = dict(
            params=dict(year=local.year, month=local.month, day=local.day,
                        hour=local.hour, minute=local.minute,
                        lat=p_geo["lat"], lon=p_geo["lon"], tz_offset=p_geo["offset"],
                        location=p_geo["label"], name="Prashna", gender=""),
            question=pq or "", cast_at=local.strftime("%d %b %Y · %H:%M"),
            offset_str=p_geo["offset_str"])

    pr = st.session_state.get("prashna")
    if not pr:
        st.info("No Prashna cast yet — enter your location above and press **Cast**.")
    else:
        pchart = compute(pr["params"])
        st.divider()
        if pr["question"]:
            st.markdown(f"**Question:** {pr['question']}")
        st.markdown(f"**Cast for:** {pr['cast_at']} ({pr['offset_str']}) · "
                    f"{pr['params']['location']}")
        if st.button("✖ Clear this Prashna"):
            st.session_state.pop("prashna", None); st.rerun()

        moon = pchart["planets"]["Moon"]
        x1, x2, x3 = st.columns(3)
        x1.metric("Prashna Lagna", f"{pchart['lagna']} {pchart['lagna_pos']}")
        x2.metric("Lagna lord", SIGN_LORDS[pchart["lagna"]])
        x3.metric("Moon", f"{moon['sign']} · {moon['nakshatra']}")

        pcol1, pcol2 = st.columns(2)
        with pcol1:
            st.markdown("**Rasi (D1) — now**")
            pd1 = {p: pchart["planets"][p]["sign_idx"] for p in pchart["planets"]}
            draw_chart(pstyle, "Prashna D1", pchart["planets"], pd1,
                       pchart["lagna_idx"], detail=True)
        with pcol2:
            st.markdown("**Navamsa (D9)**")
            draw_chart(pstyle, "Prashna D9", pchart["planets"], pchart["d9"], pchart["d9_lagna"])

        gcol1, gcol2 = st.columns(2)
        with gcol1:
            st.markdown("**Graha (Planets)**")
            st.dataframe([{"Planet": nm, "Sign": p["sign"], "Pos": p["pos"],
                           "H": p.get("house", "—"), "Nakshatra": p["nakshatra"],
                           "Lord": p["nak_lord"], "Dignity": p["dignity"]}
                          for nm in PLANET_ORDER for p in [pchart["planets"][nm]]],
                         hide_index=True, use_container_width=True)
        with gcol2:
            st.markdown("**Bhava (Houses)**")
            st.dataframe([{"House": h, "Sign": pchart["houses"][h],
                           "Lord": SIGN_LORDS[pchart["houses"][h]],
                           "Occupants": ", ".join(pchart["occupants"][h]) or "—"}
                          for h in range(1, 13)], hide_index=True, use_container_width=True)

        pan = pchart.get("panchang")
        if pan:
            st.caption(f"Panchanga now — Tithi **{pan['tithi']}** · Vara **{pan['vara']}** · "
                       f"Nakshatra **{pan['nakshatra']}** (Moon) · Yoga **{pan['yoga']}** · "
                       f"Karana **{pan['karana']}**.")
    st.caption("Classical Prashna reads the Lagna & its lord, the Moon (mind/query), and the "
               "house signifying the matter. A tool for reflection, not prediction.")
    st.stop()

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
        ok = save_chart_entry(save_key.strip() or default_key, dict(
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

st.caption("🔖 This chart is saved in the page link — **bookmark this page** "
           "(Ctrl/Cmd-D) to reopen it later with all details pre-filled.")

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
                "Varshaphala", "Vimshottari Dasha", "Jaimini", "Transits", "Panchang",
                "Yogas", "Muhurta"])

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
    st.divider()
    st.subheader("Bhava Chalit — South Indian (Pisces top-left)")
    st.caption("Houses centred on the Ascendant degree, so a planet near a sign edge falls "
               "into the adjacent bhava. Shifted planets show their rasi sign in brackets. "
               "Exact degrees & nakshatras are kept in the **D1 Rasi** (Divisional charts tab).")
    bplace = chart.get("bhava", {}).get("place")
    if bplace:
        st.markdown(bhava_grid_html(bplace, chart["planets"], chart["lagna_idx"]),
                    unsafe_allow_html=True)
    else:
        st.warning("Bhava Chalit needs the latest **astro_engine.py** (it computes the bhava "
                   "positions) — upload it and reboot.")

# ── Tab 2 ─────────────────────────────────────────────────────────────────────
with tabs[1]:
    note = "Natal positions only — transits now have their own tab." \
        if style == "South Indian" else "Fixed houses · signs rotate · Lagna at top-center."
    st.caption(f"{style} · ◆/⬩La = Lagna. {note}")
    d1 = {p: chart["planets"][p]["sign_idx"] for p in chart["planets"]}
    g1, g2 = st.columns(2)
    with g1:
        draw_chart(style, "D1 Rasi", chart["planets"], d1, chart["lagna_idx"], detail=True)
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
    jc1, jc2, jc3, jc4, jc5 = st.columns(5)
    jc1.metric("Atmakaraka (soul)", j["atmakaraka"])
    jc2.metric("Darakaraka (spouse)", j["darakaraka"])
    jc3.metric("Karakamsha", j["karakamsha"])
    jc4.metric("Arudha Lagna", j["arudha_lagna"])
    jc5.metric("Upapada Lagna", j["upapada_lagna"])
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
        f"Arudha Lagna (AL) = <b>{j['arudha_lagna']}</b> (lord {j['arudha_lagna_lord']}) · "
        f"Upapada Lagna (UL) = <b>{j['upapada_lagna']}</b> (lord {j['upapada_lagna_lord']}) · "
        f"Lagna lord {j['lagna_lord']}</div>", unsafe_allow_html=True)
    st.write("")
    cjc1, cjc2 = st.columns(2)
    with cjc1:
        st.caption("Rasi (D1) with special points · ◆ = Lagna · **AL** = Arudha Lagna · "
                   "**UL** = Upapada Lagna.")
        special = {p: chart["planets"][p]["sign_idx"] for p in chart["planets"]
                   if p != "Ascendant"}
        special["AL"] = j["arudha_lagna_si"]
        special["UL"] = j["upapada_lagna_si"]
        draw_chart(style, "Rasi + AL/UL", chart["planets"], special, chart["lagna_idx"])
    with cjc2:
        st.caption("Karakamsha chart — Navamsa (D9) read from the Atmakaraka's sign "
                   f"(◆ = {j['karakamsha']}).")
        draw_chart(style, "Karakamsha (D9)", chart["planets"], chart["d9"], j["karakamsha_si"])

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
    fd = lambda dt: dt.strftime("%d %b %Y")
    act = next((m for m in cd["mahadashas"] if m["active"]), None)
    if act:
        aad = next((a for a in act["antardashas"] if a["active"]), None)
        st.success(f"**Today:** Chara Mahadasha **{cd['current']}**"
                   + (f" → Antardasha **{aad['sign']}**" if aad else ""))
    st.markdown("**Mahadashas**")
    st.dataframe([{"Rasi": m["sign"], "Start": fd(m["start"]), "End": fd(m["end"]),
                   "Years": m["years"], "Active": "◄" if m["active"] else ""}
                  for m in cd["mahadashas"][:12]], hide_index=True, use_container_width=True)
    # antardashas — pick any mahadasha (defaults to the active one)
    labels = [f"{m['sign']}  ({fd(m['start'])} – {fd(m['end'])})" for m in cd["mahadashas"][:12]]
    di = next((i for i, m in enumerate(cd["mahadashas"][:12]) if m["active"]), 0)
    sel = st.selectbox("Antardashas of Chara Mahadasha:", labels, index=di, key="chara_ad_sel")
    chosen = cd["mahadashas"][labels.index(sel)]
    st.dataframe([{"Antardasha": f"{chosen['sign']} / {a['sign']}",
                   "Start": fd(a["start"]), "End": fd(a["end"]),
                   "Years": a["years"], "Active": "◄" if a["active"] else ""}
                  for a in chosen["antardashas"]], hide_index=True, use_container_width=True)

# ── Tab 7: Transits ───────────────────────────────────────────────────────────
with tabs[6]:
    tr = chart["transits"]; lagna = chart["lagna_idx"]
    t_lagna = chart.get("transit_lagna_idx", lagna)
    t_lpos  = chart.get("transit_lagna_pos", "")
    t_when  = chart.get("transit_local", chart["transit_date"])
    st.subheader(f"Transits — {chart['transit_date']}")
    m1, m2 = st.columns([2, 3])
    m1.metric("Lagna now (rising sign)", f"{SIGNS[t_lagna]} {t_lpos}")
    m2.caption(f"Ascendant at the moment this chart was generated — computed for the "
               f"birthplace (**{chart['meta']['location'] or '—'}**) at **{t_when}** "
               f"local time. The rising sign moves ~1°/4 min, so it depends on the exact time.")
    tpos = {p: tr[p]["sign_idx"] for p in tr if p != "Ascendant"}
    g1, g2 = st.columns(2)
    with g1:
        st.markdown("**Gochara** — transits vs **natal** houses")
        draw_chart(style, f"Transits {chart['transit_date']}", tr, tpos, lagna, detail=True)
        st.caption("House = counted from the natal Ascendant (◆). Standard transit reading.")
    with g2:
        st.markdown("**Now-chart** — houses from the **current** Lagna")
        draw_chart(style, f"Now {chart['transit_date']}", tr, tpos, t_lagna, detail=True)
        st.caption("◆ = the Lagna at chart-creation time; houses counted from it.")
    st.divider()
    akv = chart["ashtakavarga"]
    st.dataframe([{"Planet": p, "Transit sign": SIGNS[tr[p]["sign_idx"]],
                   "Pos": tr[p]["pos"],
                   "House (natal)": (tr[p]["sign_idx"] - lagna) % 12 + 1,
                   "House (now)": (tr[p]["sign_idx"] - t_lagna) % 12 + 1,
                   "Bindus": akv[p][tr[p]["sign_idx"]] if p in akv else "—",
                   "vs natal": ("same" if tr[p]["sign_idx"] == chart["planets"][p]["sign_idx"]
                                else f"{(tr[p]['sign_idx']-chart['planets'][p]['sign_idx'])%12}→")}
                  for p in PLANET_ORDER if p in tr], hide_index=True, use_container_width=True)
    st.caption("Tip: the natal Rasi (transit-free) lives in the **Divisional charts** tab. "
               "Bindus = Ashtakavarga points on the transited sign.")

# ── Tab 8: Panchang ───────────────────────────────────────────────────────────
with tabs[7]:
    pa = chart.get("panchang")
    if not pa:
        st.warning("Panchanga needs the latest **astro_engine.py** — upload it to the repo "
                   "(it contains the `compute_panchang` function), then reboot the app.")
    else:
        st.subheader("Panchanga at birth")
        st.caption("The five limbs (pañcāṅga) of the birth moment — Tithi, Vara, Nakshatra, "
                   "Yoga, Karana — from the sidereal Sun and Moon.")
        p1, p2, p3 = st.columns(3)
        p1.metric("Tithi", pa["tithi"], help=f"Lunar day {pa['tithi_num']}/30 · "
                  f"{pa['paksha']} paksha · {pa['tithi_pct']}% elapsed")
        p2.metric("Vara (weekday)", pa["vara"], help=f"Ruled by {pa['vara_lord']}")
        p3.metric("Nakshatra (Moon)", pa["nakshatra"], help=f"Ruled by {pa['nakshatra_lord']}")
        p4, p5, _ = st.columns(3)
        p4.metric("Yoga", pa["yoga"])
        p5.metric("Karana", pa["karana"])
        st.markdown(
            f"<div class='meta'>Tithi : <b>{pa['tithi']}</b> "
            f"(lunar day {pa['tithi_num']} of 30, {pa['tithi_pct']}% elapsed)<br>"
            f"Vara : <b>{pa['vara']}</b> (lord {pa['vara_lord']})<br>"
            f"Nakshatra : <b>{pa['nakshatra']}</b> (lord {pa['nakshatra_lord']})<br>"
            f"Yoga : <b>{pa['yoga']}</b> · Karana : <b>{pa['karana']}</b></div>",
            unsafe_allow_html=True)
        st.caption("Vara is taken from the local calendar day. In strict reckoning the day runs "
                   "sunrise-to-sunrise, so a birth before sunrise can fall on the previous vara.")

# ── Tab 9: Yogas ──────────────────────────────────────────────────────────────
with tabs[8]:
    yogas = chart.get("yogas")
    if yogas is None:
        st.warning("Yogas need the latest **astro_engine.py** (it contains `compute_yogas`) — "
                   "upload it to the repo and reboot.")
    else:
        st.subheader("Yogas — planetary combinations")
        st.caption("Common Parashari yogas read from the natal D1 (whole-sign houses, graha "
                   "drishti). Includes the five Mahapurusha, Raja (incl. Dharma-Karmadhipati), "
                   "Dhana, Lakshmi, Vasumati, Vipareeta Raja, Malika, and Sun/Moon yogas "
                   "(Veshi/Vasi, Sunapha/Anapha/Durudhara, Kemadruma, Gajakesari, Adhi…). "
                   "Conventions vary by school — treat this as a study aid, not a verdict.")
        GROUPS = ["Pancha Mahapurusha", "Raja", "Dhana", "Vipareeta Raja",
                  "Sun", "Moon", "Other"]
        order = {g: i for i, g in enumerate(GROUPS)}
        by = {}
        for y in yogas:
            by.setdefault(y["group"], []).append(y)
        present = [g for g in GROUPS if g in by]
        if not yogas:
            st.info("None of the checked yogas are present in this chart.")
        else:
            st.markdown(f"**{len(yogas)}** yoga(s) found · " +
                        " · ".join(f"{g} ({len(by[g])})" for g in present))
            rows = sorted(yogas, key=lambda y: order.get(y["group"], 99))
            st.dataframe([{"Group": y["group"], "Yoga": y["name"],
                           "Planets": ", ".join(y["planets"]), "What it means": y["detail"]}
                          for y in rows], hide_index=True, use_container_width=True)
        st.caption("Mahapurusha = Mars/Mercury/Jupiter/Venus/Saturn exalted or in own sign in a "
                   "kendra **from the Lagna or the Moon**. Raja = kendra-lord ↔ trikona-lord link. "
                   "Dhana = links among the 2/5/9/11 lords. Kemadruma = the Moon left unsupported "
                   "by neighbours.")

# ── Tab 10: Muhurta ───────────────────────────────────────────────────────────
with tabs[9]:
    if not hasattr(E, "compute_muhurta"):
        st.warning("Muhurta needs the latest **astro_engine.py** (it contains `compute_muhurta`) "
                   "— upload it to the repo and reboot.")
    else:
        st.subheader("Muhurta — auspicious days ahead")
        st.caption("Favourable days for an activity over the coming months — by Moon-nakshatra, "
                   "weekday, tithi, yoga and karana. Computed for the chart's place "
                   f"(**{ap['location'] or '—'}**). It samples the panchanga at **local noon** "
                   "each day (a daily approximation); the exact intraday timing (Lagna, Hora, "
                   "Rahu Kala) should still be picked for the chosen day.")
        mc1, mc2, mc3 = st.columns([3, 2, 2])
        act = mc1.selectbox("Activity", list(E.MUHURTA_ACTIVITIES.keys()), key="muh_act")
        months = int(mc2.number_input("Months ahead", min_value=1, max_value=12, value=6,
                                      key="muh_months"))
        minr = mc3.selectbox("Show", ["Excellent only", "Excellent + Good",
                                      "Fair and up", "All matches"], index=1, key="muh_rating")
        rows = muhurta(act, ap["lat"], ap["lon"], ap["tz_offset"],
                       date.today().isoformat(), months * 31)
        thr = {"Excellent only": 3, "Excellent + Good": 2,
               "Fair and up": 1, "All matches": -99}[minr]
        rows = [r for r in rows if r["score"] >= thr]
        if not rows:
            st.info("No matching days in this window — widen the months or lower the filter.")
        else:
            st.markdown(f"**{len(rows)}** day(s) suit **{act}** in the next {months} month(s).")
            st.dataframe([{"Date": r["date"], "Day": r["weekday"], "Nakshatra": r["nakshatra"],
                           "Tithi": r["tithi"], "Yoga": r["yoga"], "Karana": r["karana"],
                           "Rating": r["rating"], "Caveats": r["flags"]}
                          for r in rows], hide_index=True, use_container_width=True)
        st.caption("Rating starts from a matching nakshatra, then weighs weekday, tithi, yoga and "
                   "karana: Rikta tithis (4/9/14), Amavasya, Vishti (Bhadra) karana and malefic "
                   "yogas lower it; a favourable weekday and a waxing full-moon raise it. "
                   "Conventions vary by tradition — a study aid, not a replacement for an "
                   "astrologer's final muhurta.")


st.divider()
st.caption("For study and reflection. Matches Prokerala / astro.com when pyswisseph or "
           "JPL Horizons is available; otherwise ~0.5° built-in fallback.")
