#!/usr/bin/env python3
# Vedic Astrology (Jyotisha) Birth Chart - single-file Streamlit app.
# Charts, PDF export and chart storage are inlined here; astro_engine.py holds
# the calculations. Run: streamlit run streamlit_app.py

from datetime import date, datetime, time as dtime
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


# ========== inlined: PDF report ==========
_P_INK = "#2b2118"; _P_ACCENT = "#7b2d26"; _P_LINE = "#d9c9a8"; _P_PAPER = "#fbf7ef"
_P_GOOD = "#2e7d4f"; _P_WARN = "#b07d18"; _P_BAD = "#9a342c"; _P_LAGNA = "#fdf3df"


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
    def si_table(title, placements, lagna_si):
        natal = {i: [] for i in range(12)}
        for p, si in placements.items():
            if p != "Ascendant":
                natal[si].append(PLANET_ABR.get(p, p[:2]))
        grid_sign = {pos: si for si, pos in _SIGN_CELL.items()}
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


def draw_chart(style, label, planet_data, placements, lagna_si, detail=False, transits=None):
    if style == "North Indian":
        st.markdown(
            north_indian_svg(label, planet_data, placements, lagna_si, detail),
            unsafe_allow_html=True)
    else:
        st.markdown(
            south_indian_html(label, planet_data, placements, lagna_si, detail, transits),
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
    # auto-resolve whenever city / date / time change (offset depends on the date)
    cur_q = [city.strip().lower(), bdate.year, bdate.month, bdate.day, btime.hour, btime.minute]
    geo = st.session_state.get("geo")
    if city.strip() and (not geo or geo.get("_query") != cur_q):
        with st.spinner("Resolving location…"):
            g = E.resolve_location(city, bdate.year, bdate.month, bdate.day,
                                   btime.hour, btime.minute)
        geo = g if g else {"_notfound": True}
        geo["_query"] = cur_q
        st.session_state["geo"] = geo
    if not city.strip():
        st.sidebar.caption("Type a city — coordinates resolve automatically.")
    elif geo.get("_notfound"):
        st.sidebar.warning("City not found — check the spelling or use manual coordinates.")
    elif geo.get("offset") is None:
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

st.divider()
st.caption("For study and reflection. Matches Prokerala / astro.com when pyswisseph or "
           "JPL Horizons is available; otherwise ~0.5° built-in fallback.")
