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
