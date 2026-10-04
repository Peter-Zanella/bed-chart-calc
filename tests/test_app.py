# Reference charts checked against Swiss Ephemeris (Lahiri) by hand.
# Run: pip install -r web/requirements.txt pytest httpx && pytest -q
import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import astro_engine as E  # noqa: E402


def test_liestal_1957():
    c = E.generate_chart(1957, 8, 24, 13, 55, 47.4833, 7.7356, 1.0, "Liestal")
    assert (c["lagna"], c["lagna_pos"]) == ("Scorpio", "8° 42'")
    assert c["planets"]["Moon"]["nakshatra"] == "Ashlesha"
    assert abs(c["meta"]["ayan"] - 23.2655) < 0.001        # true Lahiri, not the swe flag
    assert c["panchang"]["vara"] == "Saturday"


def test_basel_1968_before_sunrise():
    c = E.generate_chart(1968, 3, 4, 5, 0, 47.558, 7.573, 1.0, "Basel")
    assert (c["lagna"], c["lagna_pos"]) == ("Sagittarius", "28° 39'")
    assert c["planets"]["Moon"]["pos"] == "15° 16'"
    # Monday 05:00 is before sunrise, so the Vedic day is still Sunday
    assert c["panchang"]["vara"] == "Sunday"
    later = E.generate_chart(1968, 3, 4, 9, 0, 47.558, 7.573, 1.0, "Basel")
    assert later["panchang"]["vara"] == "Monday"


def test_medical_marks_aspects_apart_from_occupants():
    import medical
    # Ketu sits in H10; the nodes act only by occupation, so its disputed
    # 9th aspect no longer reaches the 6th
    c = E.generate_chart(1990, 3, 10, 23, 58, 47.4833, 7.7356, 1.0, "Liestal")
    assert c["planets"]["Ketu"]["house"] == 10
    rows = dict(medical.compute_doshas(c)["derivation"])
    assert rows["6. Haus"] == "unbesetzt und unaspektiert"
    assert rows["Lagna"] == "Jupiter (Aspekt aus H9) → Kapha"
    # 1957 chart: Ketu occupies the 6th, so no aspect note
    c = E.generate_chart(1957, 8, 24, 13, 55, 47.4833, 7.7356, 1.0, "Liestal")
    assert dict(medical.compute_doshas(c)["derivation"])["6. Haus"] == "Ketu → Pitta"


def test_polar_day_falls_back_to_calendar_weekday():
    c = E.generate_chart(2000, 6, 21, 12, 0, 69.65, 18.96, 2.0, "Tromsø")
    assert c["panchang"]["vara"] == "Wednesday"


def test_web_api():
    from fastapi.testclient import TestClient
    from web.server import app
    cl = TestClient(app)
    r = cl.post("/api/chart", json={"date": "1957-08-24", "time": "13:55",
                                   "lat": 47.4833, "lon": 7.7356, "tz": 1})
    assert r.status_code == 200
    body = r.json()
    assert body["lagna"] == "Scorpio" and body["dashas"]["current"]["maha"]
    assert cl.post("/api/chart", json={"date": "1957-08-24", "time": "25:00",
                                      "lat": 0, "lon": 0, "tz": 0}).status_code == 422
    r = cl.post("/api/chart", json={"date": "1957-08-24", "time": "13:55", "lat": 47.4833,
                                   "lon": 7.7356, "tz": 1, "varsha_year": 2030})
    v = r.json()["varshaphala"]
    assert v["target_year"] == 2030 and v["year_number"] == 73
    assert v["muntha_sign"] == E.SIGNS[(7 + 73) % 12]     # natal Lagna Scorpio + 73 signs
    assert len(r.json()["ashtakavarga"]["Sarva"]) == 12
    assert cl.get("/").status_code == 200
    # page and scripts revalidate, so a deploy shows up without a hard reload
    assert cl.get("/app.js").headers["cache-control"] == "no-cache"


def test_web_extras():
    from fastapi.testclient import TestClient
    from web.server import app
    cl = TestClient(app)
    a = {"date": "1957-08-24", "time": "13:55", "lat": 47.4833, "lon": 7.7356, "tz": 1,
         "name": "Peter"}
    b = {"date": "1960-05-10", "time": "08:30", "lat": 47.37, "lon": 8.54, "tz": 1,
         "name": "Partner", "location": "Zürich"}
    v = cl.post("/api/compat", json={"a": a, "b": b, "male": "a"}).json()
    assert 0 <= v["total"] <= 36 and len(v["kutas"]) == 8
    r = cl.post("/api/pdf", json={"chart": a, "partner": b, "male": "a"})
    assert r.status_code == 200 and r.content[:5] == b"%PDF-"
    for name in ("medical", "fixstars", "remedies"):
        assert len(cl.post(f"/api/section/{name}", json=a).json()["html"]) > 500
    acts = cl.get("/api/muhurta/activities").json()
    m = cl.post("/api/muhurta", json={"activity": next(iter(acts)), "lat": 47.48, "lon": 7.74,
                                      "tz": 1, "start": "2026-10-01", "days": 31}).json()
    assert len(m["grid"]) == 31
    e = cl.get("/api/eclipses?start=2026&end=2026").json()
    assert e["years"]["2026"]


def test_rectify_window():
    from fastapi.testclient import TestClient
    from web.server import app
    cl = TestClient(app)
    r = cl.post("/api/rectify", json={"date": "1957-08-24", "time": "13:55", "lat": 47.4833,
                                     "lon": 7.7356, "tz": 1, "span": 30}).json()
    f = {x["key"]: x for x in r["factors"]}
    assert f["lagna"]["value"] == "Scorpio 8° 42'" and f["lagna"]["from"] is None
    assert f["moon_nak"]["value"].startswith("Ashlesha 3")
    # the D10 Lagna flips 1.6 minutes after 13:55, matching full charts either side
    assert (f["d10"]["value"], f["d10"]["to"]) == ("Virgo", "13:56:33")
    ch = next(c for c in r["changes"] if c["key"] == "d10" and c["sec"] > 0)
    assert (ch["at"], ch["from"], ch["to"]) == ("13:56:34", "Virgo", "Libra")
    for hh, mm, want in ((13, 56, "Virgo"), (13, 57, "Libra")):
        c = E.generate_chart(1957, 8, 24, hh, mm, 47.4833, 7.7356, 1.0)
        assert E.SIGNS[c["d10_lagna"]] == want
    assert r["step"] == 2 and len(r["rows"]) == 31
    mid = r["rows"][15]
    assert mid["offset"] == 0 and mid["d9"] == "Virgo" and mid["balance"] == "Mercury 7y 3m"
    # rows crossing midnight carry their own date
    r = cl.post("/api/rectify", json={"date": "1957-08-24", "time": "23:55", "lat": 47.4833,
                                     "lon": 7.7356, "tz": 1, "span": 10, "step": 5}).json()
    assert [x["date"] for x in r["rows"]][-1] == "1957-08-25"
    assert cl.post("/api/rectify", json={"date": "1957-08-24", "time": "13:55", "lat": 0,
                                        "lon": 0, "tz": 0, "span": 0}).status_code == 422


def test_observe_over_a_year():
    from web import rectify
    r = rectify.sweep(1957, 8, 24, 13, 55, 47.4833, 7.7356, 1.0, rectify.YEAR)
    assert r["mode"] == "days" and r["step"] == rectify.MONTH and len(r["rows"]) == 25
    keys = {c["key"] for c in r["changes"]}
    assert "lagna" not in keys and "moon_sign" not in keys      # cycle too fast to list
    # Mercury (Virgo 1° at birth) stations retrograde on 27 Aug 1957, then re-enters Leo
    merc = [(c["date"], c["from"], c["to"]) for c in r["changes"] if c["key"] == "Mercury"]
    assert ("1957-08-27", "Virgo", "Virgo R") in merc and ("1957-09-02", "Virgo R", "Leo R") in merc
    f = {x["key"]: x for x in r["factors"]}
    assert f["Mercury"]["value"].startswith("Virgo") and f["Mercury"]["to_date"] == "1957-08-27"
    assert r["rows"][12]["offset"] == 0 and r["rows"][12]["Mercury"] == "Virgo"
    # a week follows the Moon by nakshatra pada; a too-fine step is coarsened
    w = rectify.sweep(1957, 8, 24, 13, 55, 47.4833, 7.7356, 1.0, rectify.WEEK, step=1)
    assert any(c["key"] == "moon_nak" for c in w["changes"]) and len(w["rows"]) <= 401


def test_eclipse_hits():
    import eclipse_hits
    # conjunction, opposition and both squares count; 4° is outside the 3° orb
    h = eclipse_hits.hits(100.0, {"Sun": 101.5, "Moon": 281.0, "Mars": 10.5, "Venus": 192.0,
                                  "Saturn": 104.0, "Ascendant": 99.0})
    got = {(x["point"], x["aspect"]) for x in h}
    assert got == {("Sun", "conjunction"), ("Moon", "opposition"), ("Mars", "square"),
                   ("Venus", "square"), ("Lagna", "conjunction")}
    assert h[0]["orb"] == 0.5
    from fastapi.testclient import TestClient
    from web.server import app
    a = {"date": "1957-08-24", "time": "13:55", "lat": 47.4833, "lon": 7.7356, "tz": 1}
    r = TestClient(app).post("/api/eclipse-hits", json={**a, "year": 2026}).json()
    assert r["year"] == 2026 and r["orb"] == 3 and len(r["eclipses"]) >= 2
    assert all("hits" in e for e in r["eclipses"])
