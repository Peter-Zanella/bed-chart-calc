#!/usr/bin/env python3
# Standalone web app: a small JSON API around astro_engine.py plus a static
# front end (web/static). Run from the repo root:
#   uvicorn web.server:app --reload
# Nothing is cached per chart, so transits and the running dasha are always "now".

import os, sys
from datetime import date, datetime, time as dtime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import astro_engine as E  # noqa: E402
import eclipse_db  # noqa: E402
import pdf_report  # noqa: E402
from web import rectify  # noqa: E402

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

app = FastAPI(title="Vedic Birth Chart", docs_url="/api/docs", redoc_url=None)


@app.middleware("http")
async def revalidate_static(request, call_next):
    # Without Cache-Control the browser caches the page and scripts heuristically,
    # so after a deploy the installed app kept showing the old version.
    resp = await call_next(request)
    if not request.url.path.startswith("/api/"):
        resp.headers.setdefault("Cache-Control", "no-cache")
    return resp


def _jsonable(x):
    """Engine results hold datetimes, tuples and sets; turn them into plain JSON."""
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple, set)):
        return [_jsonable(v) for v in x]
    if isinstance(x, (datetime, date, dtime)):
        return x.isoformat()
    if isinstance(x, float) and x != x:   # NaN
        return None
    return x


class ChartIn(BaseModel):
    date: date
    time: str = Field(pattern=r"^\d{1,2}:\d{2}$")
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    tz: float = Field(ge=-14, le=14)
    location: str = ""
    name: str = ""
    gender: str = ""
    varsha_year: Optional[int] = None


def _compute(p: ChartIn) -> dict:
    hh, mm = map(int, p.time.split(":"))
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        raise HTTPException(422, "time must be HH:MM (24h)")
    return E.generate_chart(p.date.year, p.date.month, p.date.day, hh, mm,
                            p.lat, p.lon, p.tz, p.location, p.name, p.gender,
                            varsha_year=p.varsha_year)


@app.post("/api/chart")
def chart(p: ChartIn):
    return _jsonable(_compute(p))


class RectifyIn(ChartIn):
    span: int = Field(15, ge=1, le=720)      # ± minutes around the birth time
    step: int = Field(0, ge=0, le=60)        # minutes between table rows, 0 = auto


@app.post("/api/rectify")
def rectify_(p: RectifyIn):
    """Birth time rectification: what changes within ± span minutes."""
    hh, mm = map(int, p.time.split(":"))
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        raise HTTPException(422, "time must be HH:MM (24h)")
    return rectify.sweep(p.date.year, p.date.month, p.date.day, hh, mm, p.lat, p.lon, p.tz,
                         p.span, p.step)


# ── extra sections ──────────────────────────────────────────────────────────
_SECTIONS = {"medical": "medical", "fixstars": "fixstars", "remedies": "remedies"}


@app.post("/api/section/{name}")
def section(name: str, p: ChartIn):
    """HTML sections taken over from astro-report-service (German texts)."""
    if name not in _SECTIONS:
        raise HTTPException(404, "unknown section")
    mod = __import__(_SECTIONS[name])
    return {"html": mod.render_tab(_compute(p))}


@app.get("/api/eclipses")
def eclipses(start: Optional[int] = None, end: Optional[int] = None):
    y0, y1 = eclipse_db.year_range()
    return {"range": [y0, y1], "meta": eclipse_db.meta(),
            "years": _jsonable(eclipse_db.by_year(start, end))}


class MuhurtaIn(BaseModel):
    activity: str
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    tz: float = Field(ge=-14, le=14)
    start: date
    days: int = Field(31, ge=1, le=372)
    all_nak: bool = False


@app.get("/api/muhurta/activities")
def muhurta_activities():
    return {k: sorted(v["nak"]) for k, v in E.MUHURTA_ACTIVITIES.items()}


@app.post("/api/muhurta")
def muhurta(m: MuhurtaIn):
    if m.activity not in E.MUHURTA_ACTIVITIES:
        raise HTTPException(422, "unknown activity")
    rows = E.compute_muhurta(m.activity, m.lat, m.lon, m.tz, m.start, m.days, m.all_nak)
    grid = E.muhurta_grid(m.activity, m.lat, m.lon, m.tz, m.start, min(m.days, 31))
    return _jsonable({"rows": rows, "grid": grid})


class CompatIn(BaseModel):
    a: ChartIn
    b: ChartIn
    male: str = Field("a", pattern="^(a|b|unknown)$")


def _compat(c: CompatIn):
    ca, cb = _compute(c.a), _compute(c.b)
    full = E.compute_compatibility(ca, cb, male="b" if c.male == "b" else "a")
    view = pdf_report._compat_view(full)
    ma, mb = ca["planets"]["Moon"], cb["planets"]["Moon"]
    view["a"] = {"name": c.a.name or "Person A", "moon": f"{ma['sign']} · {ma['nakshatra']}"}
    view["b"] = {"name": c.b.name or "Partner", "moon": f"{mb['sign']} · {mb['nakshatra']}",
                 "loc": c.b.location}
    return ca, view


@app.post("/api/compat")
def compat(c: CompatIn):
    return _jsonable(_compat(c)[1])


class PdfIn(BaseModel):
    chart: ChartIn
    partner: Optional[ChartIn] = None
    male: str = Field("a", pattern="^(a|b|unknown)$")


@app.post("/api/pdf")
def pdf(p: PdfIn):
    cmp_pdf = None
    if p.partner:
        _, v = _compat(CompatIn(a=p.chart, b=p.partner, male=p.male))
        cmp_pdf = {"a_name": v["a"]["name"], "a_moon": v["a"]["moon"],
                   "b_name": v["b"]["name"], "b_moon": v["b"]["moon"], "b_loc": v["b"]["loc"],
                   "total": v["total"], "max": v["max"], "verdict": v["verdict"],
                   "kutas": v["kutas"], "doshas": v["doshas"], "extra": v["extra"],
                   "mangal": {"a_name": v["a"]["name"], "a": v["mangal_a"],
                              "b_name": v["b"]["name"], "b": v["mangal_b"]}}
    data = pdf_report.build_pdf(_compute(p.chart), cmp_pdf)
    fname = "vedic-chart-" + ("".join(ch for ch in p.chart.name if ch.isalnum()) or "chart") + ".pdf"
    return Response(data, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})


@app.get("/api/place")
def place(q: str = Query(min_length=2), date_: date = Query(alias="date"),
          time: str = Query("12:00", pattern=r"^\d{1,2}:\d{2}$")):
    """City → coordinates and the UTC offset valid on that date (historic DST)."""
    hh, mm = map(int, time.split(":"))
    g = E.resolve_location(q, date_.year, date_.month, date_.day, hh, mm)
    if not g:
        raise HTTPException(404, "place not found")
    return _jsonable(g)


@app.get("/api/health")
def health():
    return {"ok": True, "engine": "swisseph" if E._SWE else "fallback"}


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC, "index.html"))


app.mount("/", StaticFiles(directory=STATIC), name="static")
