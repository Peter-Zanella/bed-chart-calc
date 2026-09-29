#!/usr/bin/env python3
# Standalone web app: a small JSON API around astro_engine.py plus a static
# front end (web/static). Run from the repo root:
#   uvicorn web.server:app --reload
# Nothing is cached per chart, so transits and the running dasha are always "now".

import os, sys
from datetime import date, datetime, time as dtime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import astro_engine as E  # noqa: E402

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

app = FastAPI(title="Vedic Birth Chart", docs_url="/api/docs", redoc_url=None)


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


@app.post("/api/chart")
def chart(p: ChartIn):
    hh, mm = map(int, p.time.split(":"))
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        raise HTTPException(422, "time must be HH:MM (24h)")
    c = E.generate_chart(p.date.year, p.date.month, p.date.day, hh, mm,
                         p.lat, p.lon, p.tz, p.location, p.name, p.gender,
                         varsha_year=p.varsha_year)
    return _jsonable(c)


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
