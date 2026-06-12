#!/usr/bin/env python3
"""
Tiny JSON-file store for saved charts.

We persist only the *inputs* (date, time, place, coords, tz) — never the computed
chart — so saved entries stay small and always recompute against the latest
ephemeris and today's transits/dasha.

On Streamlit Community Cloud the filesystem is ephemeral (it resets when the app
sleeps/redeploys), so treat this as best-effort. For durable storage, point
SAVE_PATH at a mounted volume or swap in a database / gist.
"""
import json
import os
from datetime import date, datetime, time as dtime

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


def save(key: str, params: dict) -> bool:
    """params keys: name, gender, date(YYYY-MM-DD), time(HH:MM), lat, lon, tz, label."""
    data = load_all()
    data[key] = {**params, "_saved": datetime.now().isoformat(timespec="seconds")}
    return _write(data)


def delete(key: str) -> bool:
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
