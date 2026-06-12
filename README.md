# ✦ Vedic Astrology Birth Chart (Streamlit)

Jyotiṣa birth charts — Lahiri ayanamsha, whole-sign houses. Produces Rasi (D1)
with transits, Navamsa (D9), Drekkana (D3), Dasamsha (D10) in **South Indian and
North Indian** styles, Ashtakavarga, Varshaphala (solar return), the full
Vimshottari Dasha tree, and **Jaimini** (Chara Karakas with Rahu, Karakamsha,
Arudha Lagna, and Chara Dasha with Chara Bala). Includes **PDF export** and
**save/load** of charts.

## Files (only two Python files!)
    streamlit_app.py   # the whole app — UI, chart drawing, PDF export, storage
    astro_engine.py    # all astronomy / astrology calculations
    requirements.txt   # dependencies
    .streamlit/config.toml  # optional theme

Everything except the math lives in `streamlit_app.py`, so updating the app is
just replacing those files — no extra modules to keep in sync.

## Run locally
    pip install -r requirements.txt
    streamlit run streamlit_app.py

## Accuracy
The engine auto-selects the best source: pyswisseph (Swiss Ephemeris DE431,
< 0.001°) → JPL Horizons API (< 0.001°, needs internet) → built-in math (~0.5°).
With pyswisseph installed it matches Prokerala / astro.com.

## Deploy on Streamlit Community Cloud
Push to a public GitHub repo, then share.streamlit.io → Create app → pick the
repo and set the main file to `streamlit_app.py`. First build installs
requirements.txt (incl. reportlab for PDF). No API keys needed.

## Notes
- Saved charts go to `saved_charts.json` next to the app. On Streamlit Cloud the
  filesystem is ephemeral (resets when the app sleeps/redeploys) — for a
  permanent copy use the PDF download.
- Jaimini conventions vary between schools (co-lord strength, Arudha exceptions,
  antardasha start). This uses common K.N. Rao / Parashari rules.
- For study and reflection, not professional advice.
