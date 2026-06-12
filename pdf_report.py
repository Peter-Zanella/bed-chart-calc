#!/usr/bin/env python3
"""
PDF report for a computed Jyotiṣa chart, using reportlab (pure-Python).

build_pdf(chart) -> bytes      raises RuntimeError if reportlab is missing.
"""
from io import BytesIO

from astro_engine import (
    SIGNS, SIGN_ABR, SIGN_LORDS, PLANET_ORDER, PLANET_ABR, _AKV_PLANETS, _SIGN_CELL,
)

_INK = "#2b2118"; _ACCENT = "#7b2d26"; _LINE = "#d9c9a8"; _PAPER = "#fbf7ef"
_GOOD = "#2e7d4f"; _WARN = "#b07d18"; _BAD = "#9a342c"; _LAGNA = "#fdf3df"


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

    ink = colors.HexColor(_INK); accent = colors.HexColor(_ACCENT)
    line = colors.HexColor(_LINE); paper = colors.HexColor(_PAPER)
    lagna_bg = colors.HexColor(_LAGNA)
    cmap = {"good": colors.HexColor(_GOOD), "warn": colors.HexColor(_WARN),
            "bad": colors.HexColor(_BAD)}

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
    charts_row = Table(
        [[si_table("D1 Rasi", d1_pl, chart["lagna_idx"]),
          si_table("D9 Navamsa", chart["d9"], chart["d9_lagna"])]],
        colWidths=[90 * mm, 90 * mm],
    )
    charts_row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                    ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    story.append(KeepTogether(charts_row))

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
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("Generated by the Vedic Astrology Streamlit app · for study and reflection.", cap))

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=14*mm, rightMargin=14*mm,
                            topMargin=12*mm, bottomMargin=12*mm,
                            title="Vedic Birth Chart")
    doc.build(story)
    return buf.getvalue()
