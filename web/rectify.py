# Birth time rectification: how the time-sensitive parts of a chart change
# across an uncertainty window around the given birth time. Only the Lagna
# (and its vargas) and the Moon move fast enough to matter within hours, so the
# sweep reads just those two points from the engine instead of whole charts.

from datetime import datetime, timedelta, timezone

import astro_engine as E

# key, label, value from (asc, moon). Each value is something that can flip.
FACTORS = [
    ("lagna", "Lagna", lambda a, m: E.SIGNS[int(a / 30) % 12]),
    ("d9", "Navamsa Lagna (D9)", lambda a, m: E.SIGNS[E.navamsa_sign(a)]),
    ("d10", "Dasamsha Lagna (D10)", lambda a, m: E.SIGNS[E.dasamsha_sign(a)]),
    ("d3", "Drekkana Lagna (D3)", lambda a, m: E.SIGNS[E.drekkana_sign(a)]),
    ("d4", "Chaturthamsha Lagna (D4)", lambda a, m: E.SIGNS[E.chaturthamsha_sign(a)]),
    ("moon_sign", "Moon sign", lambda a, m: E.SIGNS[int(m / 30) % 12]),
    ("moon_nak", "Moon nakshatra", lambda a, m: "{} {}".format(*E.nakshatra_of(m)[::2])),
]
NICE_STEPS = (1, 2, 3, 5, 10, 15, 20, 30, 60)


def _points(local: datetime, lat: float, lon: float):
    """Sidereal Ascendant and Moon for an aware local datetime."""
    ut = local.astimezone(timezone.utc)
    jd = E.get_jd(ut.year, ut.month, ut.day, ut.hour + ut.minute / 60 + ut.second / 3600)
    if E._SWE:
        E.swe.set_sid_mode(E.swe.SIDM_LAHIRI, 0, 0)
        return E._swe_asc(jd, lat, lon), E._swe_planet("Moon", jd)
    # built-in math only: the Horizons tier would mean one web request per sample
    ayan = E._ayanamsha(jd)
    return E.norm(E._ascendant(jd, lat, lon) - ayan), E.norm(E._moon(jd) - ayan)


def _values(local, lat, lon):
    a, m = _points(local, lat, lon)
    return {k: f(a, m) for k, _, f in FACTORS}, a, m


def _pos(lon: float) -> str:
    d = lon % 30
    return f"{int(d)}° {int((d % 1) * 60):02d}'"


def _dasha(moon: float, local: datetime) -> dict:
    d = E.build_dashas(moon, local.replace(tzinfo=None))
    first = d["mahadashas"][0]
    mo = round(first["years"] * 12)
    out = {"balance": f"{first['planet']} {mo // 12}y {mo % 12}m",
           "now": " › ".join(x for x in (d["current"]["maha"], d["current"]["antar"]) if x)}
    for m in d["mahadashas"]:
        if m["active"]:
            a = next((a for a in m["antardashas"] if a["active"]), None)
            if a:
                out["antar_start"] = a["start"].date().isoformat()
    return out


def auto_step(span: int) -> int:
    """About 15 rows either side of the birth time."""
    return next((s for s in NICE_STEPS if s * 15 >= span), NICE_STEPS[-1])


def sweep(year, month, day, hour, minute, lat, lon, tz, span: int, step: int = 0) -> dict:
    birth = datetime(year, month, day, hour, minute, tzinfo=timezone(timedelta(hours=tz)))
    step = step or auto_step(span)
    labels = {k: lbl for k, lbl, _ in FACTORS}
    hms = lambda t: t.strftime("%H:%M:%S")

    # 1-minute samples find every flip (the fastest factor, the D10 Lagna, holds
    # for about 3° of the Ascendant); each flip is then bisected to the second
    samples = [(s, *_values(birth + timedelta(seconds=s), lat, lon))
               for s in range(-span * 60, span * 60 + 1, 60)]
    changes = []
    for (s0, v0, *_), (s1, v1, *_) in zip(samples, samples[1:]):
        for k in labels:
            if v0[k] == v1[k]:
                continue
            lo, hi = s0, s1
            while hi - lo > 1:
                mid = (lo + hi) // 2
                if _values(birth + timedelta(seconds=mid), lat, lon)[0][k] == v0[k]:
                    lo = mid
                else:
                    hi = mid
            t = birth + timedelta(seconds=hi)
            changes.append({"key": k, "label": labels[k], "at": hms(t), "date": t.date().isoformat(),
                            "offset": round(hi / 60, 2), "sec": hi, "from": v0[k], "to": v1[k]})
    changes.sort(key=lambda c: c["sec"])

    # how far each factor holds its birth-time value on either side
    v_birth, a_birth, m_birth = _values(birth, lat, lon)
    factors = []
    for k, lbl, _ in FACTORS:
        before = [c["sec"] for c in changes if c["key"] == k and c["sec"] <= 0]
        after = [c["sec"] for c in changes if c["key"] == k and c["sec"] > 0]
        lo, hi = (max(before) if before else None), (min(after) if after else None)
        factors.append({"key": k, "label": lbl, "value": v_birth[k],
                        "from": hms(birth + timedelta(seconds=lo)) if lo is not None else None,
                        "to": hms(birth + timedelta(seconds=hi - 1)) if hi is not None else None,
                        "minus": round(-lo / 60, 2) if lo is not None else None,
                        "plus": round(hi / 60, 2) if hi is not None else None})
    factors[0]["value"] += " " + _pos(a_birth)
    factors[-1]["value"] += f" ({_pos(m_birth)} {v_birth['moon_sign']})"

    rows = []
    for s in range(-span * 60, span * 60 + 1, step * 60):
        t = birth + timedelta(seconds=s)
        v, a, m = _values(t, lat, lon)
        rows.append({"offset": s // 60, "time": t.strftime("%H:%M"), "date": t.date().isoformat(),
                     "lagna_pos": _pos(a), "moon_pos": _pos(m), **v, **_dasha(m, t)})

    return {"birth": birth.strftime("%H:%M"), "span": span, "step": step,
            "factors": factors, "changes": changes, "rows": rows}
