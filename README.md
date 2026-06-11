# ✦ Vedic Astrology Birth Chart (Streamlit)

A web app for Jyotiṣa birth charts — Lahiri ayanamsha, whole-sign houses.
Produces Rasi (D1) with transits, Navamsa (D9), Drekkana (D3), Dasamsha (D10),
Ashtakavarga, Varshaphala (solar return), and the full Vimshottari Dasha tree.

All calculation logic lives in `astro_engine.py`; `streamlit_app.py` is only the UI.

## Accuracy
The engine picks the best available source automatically:

| Tier | Source | Accuracy | Needs |
|------|--------|----------|-------|
| 1 | `pyswisseph` (Swiss Ephemeris DE431) | < 0.001° | pip install (in `requirements.txt`) |
| 2 | JPL Horizons REST API | < 0.001° | internet |
| 3 | Built-in Meeus + Keplerian | ~0.5° | always works |

With `pyswisseph` installed, results match Prokerala / astro.com.

## Run locally
```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```
Then open the URL it prints (usually http://localhost:8501).

## Files
```
streamlit_app.py      # UI
astro_engine.py       # all astronomy/astrology math
requirements.txt      # dependencies
.streamlit/config.toml# theme
```

## Deploy free on Streamlit Community Cloud
1. Push this folder to a **public GitHub repo** (see commands below).
2. Go to https://share.streamlit.io and sign in with GitHub.
3. **Create app → From existing repo**, pick your repo/branch, set
   **Main file path** to `streamlit_app.py`, click **Deploy**.
4. First build installs `requirements.txt` (a minute or two), then you get a
   public `…streamlit.app` URL.

No secrets or API keys are needed.

## Notes
- Geocoding uses OpenStreetMap Nominatim and a timezone API — please don't
  hammer them; the lookup deliberately waits ~1s per request.
- Historical DST is resolved via `zoneinfo` + `tzdata` (e.g. Europe/Zurich was
  +01:00 in 1957, before Switzerland reintroduced summer time in 1981).
- This is for study and reflection, not professional advice.
