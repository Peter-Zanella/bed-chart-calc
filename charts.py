#!/usr/bin/env python3
"""Chart renderers for the Streamlit app: South Indian (HTML) + North Indian (SVG)."""
import astro_engine as E
from astro_engine import SIGN_ABR, PLANET_ABR, NAKSHATRAS, NAK_ABR, _SIGN_CELL

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
