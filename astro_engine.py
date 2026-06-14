#!/usr/bin/env python3
"""
Vedic Astrology (Jyotiṣa) compute engine.

This is the calculation core extracted from the original command-line script.
All astronomy / astrology math is unchanged. The terminal (ANSI) rendering and
interactive input have been removed so the same logic can drive a web UI.

Accuracy tiers — tried automatically in order:
  1. pyswisseph   Swiss Ephemeris DE431, < 0.001°   pip install pyswisseph
  2. JPL Horizons Same DE431 via REST API, < 0.001° internet required
  3. Built-in     Meeus + JPL Keplerian,  ~0.5°     always available
"""

# ── stdlib ────────────────────────────────────────────────────────────────────
import json, math, re, time, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
from typing   import Dict, List, Optional, Tuple

# ── optional path to Swiss Ephemeris .se1 ephemeris files ─────────────────────
EPHE_PATH = ""

# ── Swiss Ephemeris (pyswisseph) ──────────────────────────────────────────────
try:
    import swisseph as swe
    swe.set_ephe_path(EPHE_PATH or None)
    swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
    _SWE = True
except ImportError:
    _SWE = False

# ── zoneinfo — historically correct DST (Python 3.9+) ────────────────────────
try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    _ZONEINFO = True
except ImportError:
    _ZONEINFO = False
    ZoneInfo = None                    # type: ignore
    ZoneInfoNotFoundError = Exception  # type: ignore


# ══════════════════════════════════════════════════════════════════════════════
# ASTROLOGY DATA
# ══════════════════════════════════════════════════════════════════════════════

SIGNS = [
    "Aries","Taurus","Gemini","Cancer","Leo","Virgo",
    "Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces",
]
SIGN_ABR = ["Ari","Tau","Gem","Can","Leo","Vir","Lib","Sco","Sag","Cap","Aqu","Pis"]

SIGN_LORDS = {
    "Aries":"Mars",     "Taurus":"Venus",   "Gemini":"Mercury",
    "Cancer":"Moon",    "Leo":"Sun",         "Virgo":"Mercury",
    "Libra":"Venus",    "Scorpio":"Mars",    "Sagittarius":"Jupiter",
    "Capricorn":"Saturn","Aquarius":"Saturn","Pisces":"Jupiter",
}

NAKSHATRAS: List[Tuple[str,str]] = [
    ("Ashwini","Ketu"),          ("Bharani","Venus"),       ("Krittika","Sun"),
    ("Rohini","Moon"),           ("Mrigashira","Mars"),     ("Ardra","Rahu"),
    ("Punarvasu","Jupiter"),     ("Pushya","Saturn"),       ("Ashlesha","Mercury"),
    ("Magha","Ketu"),            ("Purva Phalguni","Venus"),("Uttara Phalguni","Sun"),
    ("Hasta","Moon"),            ("Chitra","Mars"),         ("Swati","Rahu"),
    ("Vishakha","Jupiter"),      ("Anuradha","Saturn"),     ("Jyeshtha","Mercury"),
    ("Mula","Ketu"),             ("Purva Ashadha","Venus"), ("Uttara Ashadha","Sun"),
    ("Shravana","Moon"),         ("Dhanishtha","Mars"),     ("Shatabhisha","Rahu"),
    ("Purva Bhadrapada","Jupiter"),("Uttara Bhadrapada","Saturn"),("Revati","Mercury"),
]

NAK_ABR = [
    "Asw","Bha","Kri","Roh","Mri","Ard","Pun","Pus","Ash",
    "Mag","PPh","UPh","Has","Chi","Swa","Vis","Anu","Jye",
    "Mul","PAs","UAs","Shr","Dha","Sha","PBh","UBh","Rev",
]

DASHA_ORDER = ["Ketu","Venus","Sun","Moon","Mars","Rahu","Jupiter","Saturn","Mercury"]
DASHA_YEARS = {"Ketu":7,"Venus":20,"Sun":6,"Moon":10,"Mars":7,
               "Rahu":18,"Jupiter":16,"Saturn":19,"Mercury":17}
DASHA_TOTAL = 120

EXALT_SIGN = {"Sun":0,"Moon":1,"Mars":9,"Mercury":5,"Jupiter":3,
              "Venus":11,"Saturn":6,"Rahu":1,"Ketu":7}
EXALT_DEG  = {"Sun":10,"Moon":3,"Mars":28,"Mercury":15,"Jupiter":5,
              "Venus":27,"Saturn":20,"Rahu":20,"Ketu":20}
DEBIL_SIGN = {"Sun":6,"Moon":7,"Mars":3,"Mercury":11,"Jupiter":9,
              "Venus":5,"Saturn":0,"Rahu":7,"Ketu":1}
OWN_SIGNS  = {"Sun":[4],"Moon":[3],"Mars":[0,7],"Mercury":[2,5],
              "Jupiter":[8,11],"Venus":[1,6],"Saturn":[9,10]}
MOOLA      = {"Sun":(4,0,20),"Moon":(1,4,20),"Mars":(0,0,12),
              "Mercury":(5,16,20),"Jupiter":(8,0,10),"Venus":(6,0,15),"Saturn":(9,0,20)}

PLANET_ORDER = ["Sun","Moon","Mars","Mercury","Jupiter","Venus","Saturn","Rahu","Ketu"]
PLANET_ABR   = {"Sun":"Su","Moon":"Mo","Mars":"Ma","Mercury":"Me",
                "Jupiter":"Ju","Venus":"Ve","Saturn":"Sa","Rahu":"Ra","Ketu":"Ke"}

# Ashtakavarga benefic offset tables (BPHS)
_AKV: Dict[str,Dict[str,List[int]]] = {
    "Sun":{"Sun":[1,2,4,7,8,9,10,11],"Moon":[3,6,10,11],"Mars":[1,2,4,7,8,9,10,11],
           "Mercury":[3,5,6,9,10,11,12],"Jupiter":[5,6,9,11],"Venus":[6,7,12],
           "Saturn":[1,2,4,7,8,9,10,11],"Lagna":[3,4,6,10,11,12]},
    "Moon":{"Sun":[3,6,7,8,10,11],"Moon":[1,3,6,7,10,11],"Mars":[2,3,5,6,9,10,11],
            "Mercury":[1,3,4,5,7,8,10,11],"Jupiter":[1,4,7,8,10,11],
            "Venus":[3,4,5,7,9,10,11],"Saturn":[3,5,6,11],"Lagna":[3,6,10,11]},
    "Mars":{"Sun":[3,5,6,10,11],"Moon":[3,6,11],"Mars":[1,2,4,7,8,10,11],
            "Mercury":[3,5,6,11],"Jupiter":[6,10,11,12],"Venus":[6,8,11,12],
            "Saturn":[1,4,7,8,9,10,11],"Lagna":[1,2,4,8,10,11]},
    "Mercury":{"Sun":[5,6,9,11,12],"Moon":[2,4,6,8,10,11],"Mars":[1,2,4,7,8,9,10,11],
               "Mercury":[1,3,5,6,9,10,11,12],"Jupiter":[6,8,11,12],
               "Venus":[1,2,3,4,5,8,9,11],"Saturn":[1,2,4,7,8,9,10,11],
               "Lagna":[1,2,4,6,8,10,11]},
    "Jupiter":{"Sun":[1,2,3,4,7,8,9,10,11],"Moon":[2,5,7,9,11],"Mars":[1,2,4,7,8,10,11],
               "Mercury":[1,2,4,5,6,9,10,11],"Jupiter":[1,2,3,4,7,8,10,11],
               "Venus":[2,5,6,9,10,11],"Saturn":[3,5,6,12],"Lagna":[1,2,4,5,6,7,9,10,11]},
    "Venus":{"Sun":[8,11,12],"Moon":[1,2,3,4,5,8,9,11,12],"Mars":[3,4,6,9,11,12],
             "Mercury":[3,5,6,9,11],"Jupiter":[5,8,9,10,11],"Venus":[1,2,3,4,5,8,9,10,11],
             "Saturn":[3,4,5,8,9,10,11],"Lagna":[1,2,3,4,5,8,9,11]},
    "Saturn":{"Sun":[1,2,4,7,8,9,10,11],"Moon":[3,6,11],"Mars":[3,5,6,10,11,12],
              "Mercury":[6,8,9,10,11,12],"Jupiter":[5,6,11,12],"Venus":[6,11,12],
              "Saturn":[3,5,6,11],"Lagna":[1,3,4,6,10,11]},
}
_AKV_PLANETS = ["Sun","Moon","Mars","Mercury","Jupiter","Venus","Saturn"]

# South Indian grid: sign index → (row, col)
_SIGN_CELL: Dict[int,Tuple[int,int]] = {
    11:(0,0), 0:(0,1), 1:(0,2),  2:(0,3),
    10:(1,0),                     3:(1,3),
     9:(2,0),                     4:(2,3),
     8:(3,0), 7:(3,1), 6:(3,2),  5:(3,3),
}

_WEEKDAY_LORDS = ["Sun","Moon","Mars","Mercury","Jupiter","Venus","Saturn"]
_HORA_ORDER    = ["Sun","Venus","Mercury","Moon","Saturn","Jupiter","Mars"]


# ══════════════════════════════════════════════════════════════════════════════
# TIME UTILITIES
# ══════════════════════════════════════════════════════════════════════════════

def julian_day(year:int, month:int, day:int, hour_ut:float) -> float:
    if month <= 2: year -= 1; month += 12
    A = int(year/100); B = 2 - A + int(A/4)
    return int(365.25*(year+4716)) + int(30.6001*(month+1)) + day + hour_ut/24 + B - 1524.5

def j2000c(jd:float) -> float:
    return (jd - 2451545.0) / 36525.0

def norm(a:float) -> float:
    return a % 360.0

def _jd_to_dt_str(jd:float) -> str:
    """JD → 'YYYY-MM-DD HH:MM:SS UTC' string."""
    jd2=jd+0.5; z=int(jd2); f=jd2-z
    if z>=2299161:
        a=int((z-1867216.25)/36524.25); z=z+1+a-a//4
    b=z+1524; c=int((b-122.1)/365.25); d=int(365.25*c); e=int((b-d)/30.6001)
    day2=b-d-int(30.6001*e)
    mo=e-1 if e<14 else e-13
    yr=c-4716 if mo>2 else c-4715
    hf=f*24; h=int(hf); m=int((hf-h)*60); s=int(((hf-h)*60-m)*60)
    return f"{yr}-{mo:02d}-{day2:02d} {h:02d}:{m:02d}:{s:02d} UTC"


# ══════════════════════════════════════════════════════════════════════════════
# TIER 1 — Swiss Ephemeris (pyswisseph)
# ══════════════════════════════════════════════════════════════════════════════

_SWE_ID = {"Sun":0,"Moon":1,"Mercury":2,"Venus":3,"Mars":4,"Jupiter":5,"Saturn":6,"Rahu":10}
_SWE_FL: Optional[int] = None

def _swe_planet(name:str, jd:float) -> float:
    global _SWE_FL
    if _SWE_FL is None: _SWE_FL = swe.FLG_SIDEREAL | swe.FLG_SPEED
    return norm(swe.calc_ut(jd, _SWE_ID[name], _SWE_FL)[0][0])

def _swe_asc(jd:float, lat:float, lon:float) -> float:
    return norm(swe.houses_ex(jd, lat, lon, b"W", swe.FLG_SIDEREAL)[1][0])

def _swe_ayan(jd:float) -> float:
    return swe.get_ayanamsa_ut(jd)


# ══════════════════════════════════════════════════════════════════════════════
# TIER 2 — JPL Horizons REST API  (free, no key, same DE431 as Swiss Ephemeris)
# ══════════════════════════════════════════════════════════════════════════════

_HRZ  = "https://ssd.jpl.nasa.gov/api/horizons.api"
_NAIF = {"Sun":"10","Moon":"301","Mercury":"199","Venus":"299",
         "Mars":"499","Jupiter":"599","Saturn":"699"}
_HRZ_CACHE: Dict[Tuple,float] = {}

def _hrz_fetch(planet:str, jd:float) -> Optional[float]:
    key = (planet, round(jd,5))
    if key in _HRZ_CACHE: return _HRZ_CACHE[key]
    params = {"format":"json","COMMAND":_NAIF[planet],"OBJ_DATA":"NO",
              "MAKE_EPHEM":"YES","EPHEM_TYPE":"OBSERVER","CENTER":"500@399",
              "START_TIME":f"JD{jd:.8f}","STOP_TIME":f"JD{jd+0.02:.8f}",
              "STEP_SIZE":"1d","QUANTITIES":"31","CAL_FORMAT":"JD","ANG_FORMAT":"DEG"}
    try:
        req = urllib.request.Request(_HRZ+"?"+urllib.parse.urlencode(params),
              headers={"User-Agent":"VedicAstroCalc/2.0"})
        with urllib.request.urlopen(req, timeout=12) as r:
            data = json.loads(r.read().decode())
        m = re.search(r"\$\$SOE\n(.*?)\n\$\$EOE", data.get("result",""), re.DOTALL)
        if not m: return None
        floats = [float(t) for t in m.group(1).strip().split("\n")[0].replace("*","").split()
                  if re.fullmatch(r"-?\d+\.?\d*",t)]
        if len(floats) >= 2:
            _HRZ_CACHE[key] = norm(floats[1]); return _HRZ_CACHE[key]
    except Exception: pass
    return None

def _hrz_online() -> bool:
    try:
        req = urllib.request.Request(_HRZ+"?format=json&COMMAND=499&OBJ_DATA=YES&MAKE_EPHEM=NO",
              headers={"User-Agent":"VedicAstroCalc/2.0"})
        with urllib.request.urlopen(req, timeout=5) as r: return r.status == 200
    except Exception: return False


# ══════════════════════════════════════════════════════════════════════════════
# TIER 3 — Pure-Python fallback (Meeus Sun/Moon, JPL Keplerian planets)
# ══════════════════════════════════════════════════════════════════════════════

def _ayanamsha(jd:float) -> float:
    T = j2000c(jd)
    return (23.853056 + (5029.097*T + 1.558*T*T) / 3600.0) % 360.0

def _sun(jd:float) -> float:
    T = j2000c(jd)
    L0 = 280.46646 + 36000.76983*T + 0.0003032*T*T
    M  = 357.52911 + 35999.05029*T - 0.0001537*T*T; Mr = math.radians(M%360)
    C  = ((1.914602-0.004817*T-0.000014*T*T)*math.sin(Mr)
          +(0.019993-0.000101*T)*math.sin(2*Mr)+0.000289*math.sin(3*Mr))
    return norm(L0+C-0.00569-0.00478*math.sin(math.radians(125.04-1934.136*T)))

def _moon(jd:float) -> float:
    T=j2000c(jd)
    Lp=218.3164477+481267.88123421*T-0.0015786*T*T+T**3/538841-T**4/65194000
    D =297.8501921+445267.1114034*T -0.0018819*T*T+T**3/545868-T**4/113065000
    M =357.5291092+35999.0502909*T  -0.0001536*T*T+T**3/24490000
    Mp=134.9633964+477198.8675055*T +0.0087414*T*T+T**3/69699-T**4/14712000
    F =93.2720950 +483202.0175233*T -0.0036539*T*T-T**3/3526000+T**4/863310000
    E =1.0-0.002516*T-0.0000074*T*T
    def r(x): return math.radians(x%360)
    dL=(6288774*math.sin(r(Mp))+1274027*math.sin(r(2*D-Mp))+658314*math.sin(r(2*D))
       +213618*math.sin(r(2*Mp))-185116*E*math.sin(r(M))-114332*math.sin(r(2*F))
       +58793*math.sin(r(2*D-2*Mp))+57066*E*math.sin(r(2*D-M-Mp))+53322*math.sin(r(2*D+Mp))
       +45758*E*math.sin(r(2*D-M))-40923*E*math.sin(r(Mp-M))-34720*math.sin(r(D))
       -30383*E*math.sin(r(Mp+M))+15327*math.sin(r(2*D-2*F))-12528*math.sin(r(Mp+2*F))
       +10980*math.sin(r(Mp-2*F))+10675*math.sin(r(4*D-Mp))+10034*math.sin(r(3*Mp))
       +8548*math.sin(r(4*D-2*Mp))-7888*E*math.sin(r(2*D+M-Mp))-6766*E*math.sin(r(2*D+M))
       -5163*math.sin(r(D-Mp))+4987*E*math.sin(r(D+M))+4036*E*math.sin(r(2*D-M+Mp))
       +3994*math.sin(r(2*D+2*Mp))+3861*math.sin(r(4*D))+3665*math.sin(r(2*D-3*Mp))
       -2689*E*math.sin(r(M-2*Mp))-2602*math.sin(r(2*(D-Mp)))+2390*E*math.sin(r(2*D-M-2*Mp))
       -2348*math.sin(r(D+Mp))+2236*E*math.sin(r(2*D-2*M))-2120*E*math.sin(r(2*Mp+M))
       -2069*E*E*math.sin(r(2*M))+2048*E*math.sin(r(2*D-2*M-Mp))-1773*math.sin(r(2*D+Mp-2*F))
       -1595*math.sin(r(2*(D+F)))+1215*E*math.sin(r(4*D-M-Mp))-1110*math.sin(r(2*Mp+2*F))
       -892*math.sin(r(3*D-Mp))-810*E*math.sin(r(2*D+M+Mp))+759*E*math.sin(r(4*D-M-2*Mp))
       -713*E*E*math.sin(r(Mp-2*M))-700*E*E*math.sin(r(2*D+2*M-Mp))
       +691*E*math.sin(r(2*D+M-2*Mp))+596*E*math.sin(r(2*D-M-2*F))+549*math.sin(r(4*D+Mp))
       +537*math.sin(r(4*Mp))+520*E*math.sin(r(4*D-M))-487*math.sin(r(D-2*Mp))
       -399*E*math.sin(r(2*D+M-2*F))-381*math.sin(r(2*Mp-2*F))+351*E*math.sin(r(D+M+Mp))
       -340*math.sin(r(3*D-2*Mp))+330*math.sin(r(4*D-3*Mp))+327*E*math.sin(r(2*D-M+2*Mp))
       -323*E*E*math.sin(r(2*M+Mp))+299*E*math.sin(r(D+M-Mp))+294*math.sin(r(2*D+3*Mp))
       )/1_000_000.0
    return norm(Lp+dL)

def _rahu(jd:float) -> float:
    T=j2000c(jd)
    return norm(125.04452-1934.136261*T+0.0020708*T*T+T**3/450000.0)

_JPL: Dict[str,List[float]] = {
    "Mercury":[0.38709927,0.00000037,0.20563593,0.00001906,7.00497902,-0.00594749,
               252.25032350,149472.67411175,77.45779628,0.16047689,48.33076593,-0.12534081],
    "Venus":  [0.72333566,0.00000390,0.00677672,-0.00004107,3.39467605,-0.00078890,
               181.97909950,58517.81538729,131.60246718,0.00268329,76.67984255,-0.27769418],
    "Earth":  [1.00000261,0.00000562,0.01671123,-0.00004392,-0.00001531,-0.01294668,
               100.46457166,35999.37244981,102.93768193,0.32327364,0.0,0.0],
    "Mars":   [1.52371034,0.00001847,0.09339410,0.00007882,1.84969142,-0.00813131,
               -4.55343205,19140.30268499,-23.94362959,0.44441088,49.55953891,-0.29257343],
    "Jupiter":[5.20288700,-0.00011607,0.04838624,-0.00013253,1.30439695,-0.00183714,
               34.39644051,3034.74612775,14.72847983,0.21252668,100.47390909,0.20469106],
    "Saturn": [9.53667594,-0.00125060,0.05386179,-0.00050991,2.48599187,0.00193609,
               49.95424423,1222.49514316,92.59887831,-0.41897216,113.66242448,-0.28867794],
}

def _kepler(body:str, jd:float) -> Tuple[float,float]:
    el=_JPL[body]; T=j2000c(jd)
    e=el[2]+el[3]*T; L=norm(el[6]+el[7]*T); w=norm(el[8]+el[9]*T); M=norm(L-w)
    E=math.radians(M)
    for _ in range(20):
        dE=(math.radians(M)-E+e*math.sin(E))/(1-e*math.cos(E)); E+=dE
        if abs(dE)<1e-12: break
    v=2*math.degrees(math.atan2(math.sqrt(1+e)*math.sin(E/2),math.sqrt(1-e)*math.cos(E/2)))
    return norm(v+w),(el[0]+el[1]*T)*(1-e*math.cos(E))

def _planet(name:str, jd:float) -> float:
    EL,ER=_kepler("Earth",jd); Ex,Ey=ER*math.cos(math.radians(EL)),ER*math.sin(math.radians(EL))
    PL,PR=_kepler(name,jd); Px,Py=PR*math.cos(math.radians(PL)),PR*math.sin(math.radians(PL))
    return norm(math.degrees(math.atan2(Py-Ey,Px-Ex)))

def _ascendant(jd:float, lat:float, lon:float) -> float:
    T=j2000c(jd)
    RAMC=norm(280.46061837+360.98564736629*(jd-2451545)+0.000387933*T*T-T**3/38710000+lon)
    eps=23.439291111-0.013004167*T-1.6389e-7*T*T+5.0361e-7*T**3
    E,e,la=math.radians(RAMC),math.radians(eps),math.radians(lat)
    return norm(math.degrees(math.atan2(math.cos(E),-(math.sin(E)*math.cos(e)+math.tan(la)*math.sin(e)))))


# ══════════════════════════════════════════════════════════════════════════════
# ENGINE — selects best available tier automatically
# ══════════════════════════════════════════════════════════════════════════════

_hrz_checked: Optional[bool] = None

def compute_positions(jd:float, lat:float, lon:float) -> Tuple[Dict[str,float],float,str]:
    """Return ({graha: sidereal_lon}, ayanamsha, engine_label). Tries tiers 1→2→3."""
    global _hrz_checked

    if _SWE:
        ayan = _swe_ayan(jd)
        lons = {p: _swe_planet(p,jd) for p in ("Sun","Moon","Mercury","Venus","Mars","Jupiter","Saturn","Rahu")}
        lons["Ketu"] = norm(lons["Rahu"]+180); lons["Ascendant"] = _swe_asc(jd,lat,lon)
        return lons, ayan, "Swiss Ephemeris (pyswisseph)  —  DE431, < 0.001°"

    if _hrz_checked is None:
        _hrz_checked = _hrz_online()

    if _hrz_checked:
        ayan = _ayanamsha(jd); lons = {}; ok = True
        for p in ("Sun","Moon","Mercury","Venus","Mars","Jupiter","Saturn"):
            t = _hrz_fetch(p, jd)
            if t is None: ok = False; break
            lons[p] = norm(t - ayan)
        if ok:
            lons["Rahu"] = norm(_rahu(jd)-ayan); lons["Ketu"] = norm(lons["Rahu"]+180)
            lons["Ascendant"] = norm(_ascendant(jd,lat,lon)-ayan)
            return lons, ayan, "JPL Horizons API  —  DE431, < 0.001°"
        _hrz_checked = False

    ayan = _ayanamsha(jd); lons = {}
    for p in ("Sun","Moon","Mercury","Venus","Mars","Jupiter","Saturn","Rahu"):
        t = _sun(jd) if p=="Sun" else _moon(jd) if p=="Moon" else _rahu(jd) if p=="Rahu" else _planet(p,jd)
        lons[p] = norm(t - ayan)
    lons["Ketu"] = norm(lons["Rahu"]+180)
    lons["Ascendant"] = norm(_ascendant(jd,lat,lon)-ayan)
    return lons, ayan, "Built-in math (JPL Keplerian)  —  ~0.5° for planets"

def get_jd(year:int, month:int, day:int, hour_ut:float) -> float:
    return swe.julday(year,month,day,hour_ut) if _SWE else julian_day(year,month,day,hour_ut)


# ══════════════════════════════════════════════════════════════════════════════
# ASTROLOGY HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def sign_of(lon:float) -> Tuple[int,str,float]:
    idx = int(lon/30)%12; return idx, SIGNS[idx], lon%30

def nakshatra_of(lon:float) -> Tuple[str,str,int]:
    span=360/27; idx=int(lon/span)%27; pada=int((lon%span)/(span/4))+1
    return NAKSHATRAS[idx][0], NAKSHATRAS[idx][1], pada

def dignity_of(planet:str, si:int, deg:float) -> str:
    if planet in ("Rahu","Ketu"):
        if EXALT_SIGN.get(planet)==si: return "Exalted"
        if DEBIL_SIGN.get(planet)==si: return "Debilitated"
        return "—"
    if EXALT_SIGN.get(planet)==si:
        return "Exalted"+(" (exact)" if abs(deg-EXALT_DEG.get(planet,-1))<1 else "")
    if DEBIL_SIGN.get(planet)==si: return "Debilitated"
    mt=MOOLA.get(planet)
    if mt and si==mt[0] and mt[1]<=deg<=mt[2]: return "Moolatrikona"
    if si in OWN_SIGNS.get(planet,[]): return "Own Sign"
    return "—"

def _planet_record(name:str, lon:float) -> Dict:
    """Build a complete planet data record from a sidereal longitude."""
    si,sn,di = sign_of(lon); nak,nl,pada = nakshatra_of(lon)
    return {"lon":round(lon,4),"sign_idx":si,"sign":sn,"sign_lord":SIGN_LORDS[sn],
            "pos":f"{int(di)}° {int((di%1)*60):02d}'","nakshatra":nak,"nak_lord":nl,
            "pada":pada,"dignity":dignity_of(name,si,di) if name!="Ascendant" else "—"}


# ══════════════════════════════════════════════════════════════════════════════
# DIVISIONAL CHARTS
# ══════════════════════════════════════════════════════════════════════════════

_D9_START = [0,9,6,3,0,9,6,3,0,9,6,3]   # navamsa start by natal sign

def navamsa_sign(lon:float) -> int:
    sign=int(lon/30)%12; part=int((lon%30)/(30/9))
    return (_D9_START[sign]+part)%12

def drekkana_sign(lon:float) -> int:
    sign=int(lon/30)%12; return (sign+int((lon%30)/10)*4)%12

def dasamsha_sign(lon:float) -> int:
    sign=int(lon/30)%12; start=sign if sign%2==0 else (sign+8)%12
    return (start+int((lon%30)/3))%12

def divisional_sign(lon:float, div:int) -> int:
    if div==9:  return navamsa_sign(lon)
    if div==3:  return drekkana_sign(lon)
    if div==10: return dasamsha_sign(lon)
    return int(lon/30)%12

def compute_divisional(lons:Dict[str,float], div:int) -> Dict[str,int]:
    return {name: divisional_sign(lon, div) for name,lon in lons.items()}


# ══════════════════════════════════════════════════════════════════════════════
# ASHTAKAVARGA
# ══════════════════════════════════════════════════════════════════════════════

def compute_ashtakavarga(natal_signs:Dict[str,int]) -> Dict[str,List[int]]:
    """Bhinnashtakavarga for 7 planets + Sarvashtakavarga."""
    result: Dict[str,List[int]] = {}
    for planet in _AKV_PLANETS:
        bindus = [0]*12
        for sign in range(12):
            for contributor, benefic in _AKV[planet].items():
                c_sign = natal_signs.get("Ascendant" if contributor=="Lagna" else contributor, 0)
                if (sign - c_sign) % 12 + 1 in benefic:
                    bindus[sign] += 1
        result[planet] = bindus
    result["Sarva"] = [sum(result[p][s] for p in _AKV_PLANETS) for s in range(12)]
    return result


# ══════════════════════════════════════════════════════════════════════════════
# VIMSHOTTARI DASHA
# ══════════════════════════════════════════════════════════════════════════════

def build_dashas(moon_sid:float, birth_dt:datetime) -> Dict:
    """9-period Mahadasha tree with Antardashas and Pratyantardashas."""
    span=360/27; nak_idx=int(moon_sid/span)%27
    lord=NAKSHATRAS[nak_idx][1]; frac_done=(moon_sid%span)/span
    start_idx=DASHA_ORDER.index(lord); today=datetime.now()
    cur_maha=cur_antar=cur_pad=None
    mahas=[]; maha_curr=birth_dt

    for i in range(9):
        maha=DASHA_ORDER[(start_idx+i)%9]; full_yrs=DASHA_YEARS[maha]
        maha_yrs=full_yrs*(1-frac_done if i==0 else 1.0)
        maha_end=maha_curr+timedelta(days=maha_yrs*365.25)
        abs_start=maha_curr-timedelta(days=frac_done*full_yrs*365.25) if i==0 else maha_curr
        maha_i=DASHA_ORDER.index(maha); ad_cur=abs_start; ads=[]

        for j in range(9):
            antar=DASHA_ORDER[(maha_i+j)%9]
            ad_yrs=full_yrs*DASHA_YEARS[antar]/DASHA_TOTAL
            ad_end=ad_cur+timedelta(days=ad_yrs*365.25)
            if ad_end<=birth_dt: ad_cur=ad_end; continue
            ad_start=max(birth_dt,ad_cur)
            antar_i=DASHA_ORDER.index(antar); pad_cur=ad_cur; pads=[]

            for k in range(9):
                prat=DASHA_ORDER[(antar_i+k)%9]
                pad_yrs=full_yrs*DASHA_YEARS[antar]*DASHA_YEARS[prat]/(DASHA_TOTAL**2)
                pad_end=pad_cur+timedelta(days=pad_yrs*365.25)
                pad_start=max(ad_start,pad_cur)
                if pad_start<pad_end:
                    active=pad_start<=today<pad_end
                    pads.append({"planet":prat,"start":pad_start,"end":pad_end,
                                 "years":round(pad_yrs,4),"active":active})
                    if active: cur_pad=prat
                pad_cur=pad_end

            active=ad_start<=today<ad_end
            ads.append({"planet":antar,"start":ad_start,"end":ad_end,
                        "years":round(ad_yrs,4),"active":active,"pratyantardashas":pads})
            if active: cur_antar=antar
            ad_cur=ad_end

        active=maha_curr<=today<maha_end
        mahas.append({"planet":maha,"start":maha_curr,"end":maha_end,
                      "years":round(maha_yrs,2),"active":active,"antardashas":ads})
        if active: cur_maha=maha
        maha_curr=maha_end

    return {"mahadashas":mahas,"current":{"maha":cur_maha,"antar":cur_antar,"pratyantar":cur_pad}}


# ══════════════════════════════════════════════════════════════════════════════
# VARSHAPHALA  (Solar Return / Annual Horoscope)
# ══════════════════════════════════════════════════════════════════════════════

def _sun_sid(jd:float) -> float:
    return norm(_sun(jd) - _ayanamsha(jd))

def find_solar_return_jd(natal_sun_sid:float, birth_month:int,
                          birth_day:int, target_year:int) -> float:
    centre = julian_day(target_year, birth_month, birth_day, 12)
    a, b   = centre - 40, centre + 40
    def diff(jd):
        d = _sun_sid(jd) - natal_sun_sid
        if d > 180: d -= 360
        if d < -180: d += 360
        return d
    for _ in range(60):
        mid = (a+b)/2
        if diff(a)*diff(mid) <= 0: b = mid
        else: a = mid
        if abs(b-a) < 1e-8: break
    return (a+b)/2

def compute_varshaphala(birth_year:int, birth_month:int, birth_day:int,
                        natal_sun_sid:float, natal_lagna_si:int,
                        lat:float, lon:float, target_year:int) -> Dict:
    jd_sr = find_solar_return_jd(natal_sun_sid, birth_month, birth_day, target_year)
    lons_sr, _, _ = compute_positions(jd_sr, lat, lon)

    planets_sr = {name: _planet_record(name, lon) for name,lon in lons_sr.items()}

    asc_si    = planets_sr["Ascendant"]["sign_idx"]
    asc_sn    = SIGNS[asc_si]
    lagna_lord = SIGN_LORDS[asc_sn]

    age      = target_year - birth_year
    mun_si   = (natal_lagna_si + age) % 12

    wd_lord  = _WEEKDAY_LORDS[int(jd_sr+1.5)%7]
    hl_start = _HORA_ORDER.index(_WEEKDAY_LORDS[int(jd_sr+1.5)%7])
    hr_lord  = _HORA_ORDER[(hl_start + int((jd_sr+0.5)%1*24)) % 7]
    candidates = [wd_lord, hr_lord, lagna_lord]
    varsha_pati = max(set(candidates), key=candidates.count)

    return {
        "year_number":   age,
        "target_year":   target_year,
        "jd_return":     round(jd_sr,5),
        "return_dt_utc": _jd_to_dt_str(jd_sr),
        "planets":       planets_sr,
        "lagna":         asc_sn,
        "lagna_pos":     planets_sr["Ascendant"]["pos"],
        "lagna_si":      asc_si,
        "lagna_lord":    lagna_lord,
        "muntha_sign":   SIGNS[mun_si],
        "muntha_si":     mun_si,
        "muntha_lord":   SIGN_LORDS[SIGNS[mun_si]],
        "varsha_pati":   varsha_pati,
        "weekday_lord":  wd_lord,
        "hora_lord":     hr_lord,
        "ashtakavarga":  compute_ashtakavarga(
            {p: planets_sr[p]["sign_idx"] for p in planets_sr}),
    }


# ══════════════════════════════════════════════════════════════════════════════
# JAIMINI  (Chara Karakas — 8-karaka scheme including Rahu)
#
# Each graha is ranked by the degrees it has traversed within its sign (0–30°),
# highest first. Rahu is reckoned in REVERSE (30° − deg) because it moves
# retrograde — this is what "taking Rahu into account" means and is the
# difference between the 7-karaka (no Rahu) and 8-karaka schemes.
#   1 Atmakaraka (AK)   soul / self          highest degree
#   2 Amatyakaraka(AmK) career / advisor
#   3 Bhratrikaraka(BK) siblings
#   4 Matrikaraka (MK)  mother
#   5 Pitrikaraka (PiK) father
#   6 Putrakaraka (PuK) children
#   7 Gnatikaraka (GK)  cousins / obstacles
#   8 Darakaraka (DK)   spouse               lowest degree
# ══════════════════════════════════════════════════════════════════════════════

CHARA_KARAKAS_8 = ["Atmakaraka", "Amatyakaraka", "Bhratrikaraka", "Matrikaraka",
                   "Pitrikaraka", "Putrakaraka", "Gnatikaraka", "Darakaraka"]
CHARA_ABR = {"Atmakaraka": "AK", "Amatyakaraka": "AmK", "Bhratrikaraka": "BK",
             "Matrikaraka": "MK", "Pitrikaraka": "PiK", "Putrakaraka": "PuK",
             "Gnatikaraka": "GK", "Darakaraka": "DK"}
CHARA_MEANING = {"Atmakaraka": "soul / self", "Amatyakaraka": "career / advisor",
                 "Bhratrikaraka": "siblings", "Matrikaraka": "mother",
                 "Pitrikaraka": "father", "Putrakaraka": "children",
                 "Gnatikaraka": "cousins / obstacles", "Darakaraka": "spouse"}


def _arudha(house_si: int, lord_si: int) -> int:
    """Arudha pada of a sign: count house→lord, same count from lord; 1st/7th → 10th."""
    al = (2 * lord_si - house_si) % 12
    if al == house_si or al == (house_si + 6) % 12:
        al = (al + 9) % 12   # 10th from the computed pada
    return al


def compute_jaimini(lons: Dict[str, float], lagna_si: int) -> Dict:
    """Chara Karakas (8, including Rahu), Karakamsha, and Arudha Lagna."""
    grahas = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu"]
    scored = []
    for g in grahas:
        deg = lons[g] % 30
        eff = (30 - deg) if g == "Rahu" else deg     # Rahu reckoned in reverse
        scored.append((g, eff, deg))
    scored.sort(key=lambda x: x[1], reverse=True)

    karakas, karaka_of = {}, {}
    for i, (g, eff, deg) in enumerate(scored):
        role = CHARA_KARAKAS_8[i]
        si, sn, _ = sign_of(lons[g])
        karakas[role] = {"planet": g, "sign": sn, "sign_idx": si,
                         "deg_in_sign": round(deg, 4), "effective": round(eff, 4),
                         "reverse": g == "Rahu"}
        karaka_of[g] = role

    ak = karakas["Atmakaraka"]["planet"]
    dk = karakas["Darakaraka"]["planet"]
    karakamsha_si = navamsa_sign(lons[ak])              # AK's navamsa sign

    lagna_lord = SIGN_LORDS[SIGNS[lagna_si]]
    lord_si = sign_of(lons[lagna_lord])[0]
    al_si = _arudha(lagna_si, lord_si)

    # Upapada Lagna (UL) — arudha pada of the 12th house
    twelfth_si = (lagna_si - 1) % 12
    twelfth_lord = SIGN_LORDS[SIGNS[twelfth_si]]
    ul_si = _arudha(twelfth_si, sign_of(lons[twelfth_lord])[0])

    return {
        "order": CHARA_KARAKAS_8,
        "karakas": karakas,
        "karaka_of": karaka_of,
        "atmakaraka": ak,
        "darakaraka": dk,
        "karakamsha_si": karakamsha_si,
        "karakamsha": SIGNS[karakamsha_si],
        "karakamsha_lord": SIGN_LORDS[SIGNS[karakamsha_si]],
        "arudha_lagna_si": al_si,
        "arudha_lagna": SIGNS[al_si],
        "arudha_lagna_lord": SIGN_LORDS[SIGNS[al_si]],
        "upapada_lagna_si": ul_si,
        "upapada_lagna": SIGNS[ul_si],
        "upapada_lagna_lord": SIGN_LORDS[SIGNS[ul_si]],
        "lagna_lord": lagna_lord,
    }


# ══════════════════════════════════════════════════════════════════════════════
# CHARA DASHA  (Jaimini sign-based dasha — K.N. Rao method)
#
#  • Start at the Lagna sign at birth.
#  • Sequence direction: forward (zodiacal) if Lagna is an ODD sign
#    (Aries, Gemini, Leo, Libra, Sagittarius, Aquarius), else backward.
#  • Duration of a sign = (count from the sign to its lord) − 1 year, where the
#    count direction is forward for odd signs and backward for even signs; a
#    count of 1 (lord in the sign) gives 12 years.
#  • Dual-ruled signs: Scorpio (Mars/Ketu), Aquarius (Saturn/Rahu) — the longer
#    of the two co-lord periods is used (a common convention; schools vary).
#  • Antardashas: each = mahadasha/12, starting from the mahadasha sign and
#    moving in that sign's own direction (its odd/even nature).
# ══════════════════════════════════════════════════════════════════════════════

def _chara_odd(si: int) -> bool:
    """Odd sign? Aries, Gemini, Leo, Libra, Sagittarius, Aquarius (0-based even index)."""
    return si % 2 == 0

def _chara_count(from_si: int, to_si: int, direct: bool) -> int:
    return ((to_si - from_si) % 12 + 1) if direct else ((from_si - to_si) % 12 + 1)

# ── Jaimini sign-strength helpers (Chara Bala) ────────────────────────────────
_MOVABLE = {0, 3, 6, 9}    # Aries, Cancer, Libra, Capricorn
_FIXED   = {1, 4, 7, 10}   # Taurus, Leo, Scorpio, Aquarius
_DUAL    = {2, 5, 8, 11}   # Gemini, Virgo, Sagittarius, Pisces
_BALA_GRAHAS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]

def _rasi_aspects(si: int) -> List[int]:
    """Signs aspected by the sign at si (Jaimini Rasi Drishti)."""
    if si in _MOVABLE:
        nxt = (si + 1) % 12
        return [s for s in _FIXED if s != nxt]      # movable → fixed, minus the next sign
    if si in _FIXED:
        prev = (si - 1) % 12
        return [s for s in _MOVABLE if s != prev]   # fixed → movable, minus the previous sign
    return [s for s in _DUAL if s != si]            # dual → the other dual signs

def _conjunct_count(ps: Dict[str, int], p: str) -> int:
    return sum(1 for q in _BALA_GRAHAS if q != p and ps.get(q) == ps[p])

def _aspect_count(ps: Dict[str, int], p: str) -> int:
    si = ps[p]
    return sum(1 for q in _BALA_GRAHAS if q != p and si in _rasi_aspects(ps[q]))

def _dignity_rank(p: str, ps: Dict[str, int], lons: Dict[str, float]) -> int:
    d = dignity_of(p, ps[p], lons[p] % 30)
    if d.startswith("Exalted"):     return 3
    if d == "Moolatrikona":         return 2
    if d == "Own Sign":             return 1
    if d == "Debilitated":          return -1
    return 0

def stronger_colord(sign_si: int, a: str, b: str,
                    ps: Dict[str, int], lons: Dict[str, float]) -> Tuple[str, str]:
    """Pick the stronger co-lord by Jaimini criteria, in order. Returns (lord, reason)."""
    in_a, in_b = ps[a] == sign_si, ps[b] == sign_si
    if in_a != in_b:
        return (a, "in the sign") if in_a else (b, "in the sign")
    ca, cb = _conjunct_count(ps, a), _conjunct_count(ps, b)
    if ca != cb:
        return (a if ca > cb else b, "more conjunctions")
    aa, ab = _aspect_count(ps, a), _aspect_count(ps, b)
    if aa != ab:
        return (a if aa > ab else b, "more aspects (rasi drishti)")
    da, db = _dignity_rank(a, ps, lons), _dignity_rank(b, ps, lons)
    if da != db:
        return (a if da > db else b, "dignity")
    ga, gb = lons[a] % 30, lons[b] % 30
    if abs(ga - gb) > 1e-9:
        return (a if ga > gb else b, "higher degree")
    return (b, "tie → node")   # deterministic final fallback

def _chara_years(sign_si: int, ps: Dict[str, int],
                 lons: Dict[str, float]) -> Tuple[int, str, str]:
    """Return (years, lord_used, reason). reason is '' for single-lord signs."""
    direct = _chara_odd(sign_si)
    sn = SIGNS[sign_si]
    if sn == "Scorpio":
        lord, reason = stronger_colord(sign_si, "Mars", "Ketu", ps, lons)
    elif sn == "Aquarius":
        lord, reason = stronger_colord(sign_si, "Saturn", "Rahu", ps, lons)
    else:
        lord, reason = SIGN_LORDS[sn], ""
    y = _chara_count(sign_si, ps[lord], direct) - 1
    return (12 if y == 0 else y), lord, reason

def _chara_antardashas(maha_si: int, maha_years: float, start_dt: datetime,
                       today: datetime) -> List[Dict]:
    direct = _chara_odd(maha_si)
    sub = maha_years / 12.0
    out, cur = [], start_dt
    for i in range(12):
        si = (maha_si + i) % 12 if direct else (maha_si - i) % 12
        end = cur + timedelta(days=sub * 365.25)
        out.append({"sign": SIGNS[si], "sign_idx": si, "start": cur, "end": end,
                    "years": round(sub, 3), "active": cur <= today < end})
        cur = end
    return out

def build_chara_dasha(planet_signs: Dict[str, int], lons: Dict[str, float],
                      lagna_si: int, birth_dt: datetime, span_years: float = 120.0) -> Dict:
    direct = _chara_odd(lagna_si)
    order = [((lagna_si + i) % 12 if direct else (lagna_si - i) % 12) for i in range(12)]

    durations, colords = {}, {}
    for si in range(12):
        yrs, lord, reason = _chara_years(si, planet_signs, lons)
        durations[si] = yrs
        if SIGNS[si] in ("Scorpio", "Aquarius"):
            colords[SIGNS[si]] = {"lord": lord, "reason": reason}

    today = datetime.now()
    mahas, cur, total, idx, current = [], birth_dt, 0.0, 0, None
    while total < span_years:
        si = order[idx % 12]
        yrs = durations[si]
        end = cur + timedelta(days=yrs * 365.25)
        active = cur <= today < end
        mahas.append({"sign": SIGNS[si], "sign_idx": si, "start": cur, "end": end,
                      "years": yrs, "active": active,
                      "antardashas": _chara_antardashas(si, yrs, cur, today)})
        if active:
            current = SIGNS[si]
        cur = end; total += yrs; idx += 1

    return {"mahadashas": mahas, "current": current,
            "direction": "direct (zodiacal)" if direct else "reverse",
            "durations": {SIGNS[si]: durations[si] for si in range(12)},
            "colords": colords}


# ══════════════════════════════════════════════════════════════════════════════
# GEOCODING  (Nominatim → IANA timezone → zoneinfo for historical DST)
# ══════════════════════════════════════════════════════════════════════════════

_UA = {"User-Agent":"VedicAstroCalc/2.0","Accept":"application/json"}

def _http_get(url:str) -> Optional[dict]:
    try:
        req = urllib.request.Request(url, headers=_UA)
        with urllib.request.urlopen(req, timeout=8) as r: return json.loads(r.read().decode())
    except Exception: return None

def geocode(query:str) -> Optional[Dict]:
    time.sleep(1)
    data = _http_get("https://nominatim.openstreetmap.org/search"
                     f"?q={urllib.parse.quote_plus(query)}&format=json&limit=3&addressdetails=1")
    if not data: return None
    prefer = {"city","town","village","suburb","municipality","county","state","country","administrative"}
    results = [r for r in data if r.get("type","") in prefer] or data
    if not results: return None
    r=results[0]; addr=r.get("address",{})
    city=addr.get("city") or addr.get("town") or addr.get("village") or addr.get("county") or query
    return {"lat":float(r["lat"]),"lon":float(r["lon"]),
            "label":f"{city}, {addr.get('country','')}".rstrip(", ")}

def iana_tz(lat:float, lon:float) -> Optional[str]:
    d = _http_get(f"https://timeapi.io/api/timezone/coordinate?latitude={lat:.6f}&longitude={lon:.6f}")
    return d.get("timeZone") if d else None

def hist_offset(iana:str, year:int, month:int, day:int, hour:int, minute:int) -> Optional[float]:
    if not _ZONEINFO: return None
    try:
        dt = datetime(year,month,day,hour,minute,tzinfo=ZoneInfo(iana))
        return dt.utcoffset().total_seconds()/3600
    except (ZoneInfoNotFoundError, Exception): return None

def resolve_location(city:str, year:int, month:int, day:int,
                     hour:int, minute:int) -> Optional[Dict]:
    """Geocode a place + resolve historically-correct UTC offset. No console output."""
    geo = geocode(city)
    if not geo: return None
    iana = iana_tz(geo["lat"], geo["lon"])
    offset = hist_offset(iana, year, month, day, hour, minute) if iana else None
    off_str = ""
    if offset is not None:
        h,m=int(abs(offset)),int(round((abs(offset)%1)*60)); s="+" if offset>=0 else "-"
        off_str=f"UTC{s}{h:02d}:{m:02d}"
    return {**geo, "iana":iana, "offset":offset, "offset_str":off_str}


# ══════════════════════════════════════════════════════════════════════════════
# PANCHANGA (five limbs at the birth moment)
# ══════════════════════════════════════════════════════════════════════════════
TITHI_NAMES = ["Pratipada", "Dvitiya", "Tritiya", "Chaturthi", "Panchami", "Shashthi",
               "Saptami", "Ashtami", "Navami", "Dashami", "Ekadashi", "Dvadashi",
               "Trayodashi", "Chaturdashi", "Purnima"]
YOGA_NAMES = ["Vishkambha", "Priti", "Ayushman", "Saubhagya", "Shobhana", "Atiganda",
              "Sukarma", "Dhriti", "Shula", "Ganda", "Vriddhi", "Dhruva", "Vyaghata",
              "Harshana", "Vajra", "Siddhi", "Vyatipata", "Variyana", "Parigha", "Shiva",
              "Siddha", "Sadhya", "Shubha", "Shukla", "Brahma", "Indra", "Vaidhriti"]
KARANA_MOVABLE = ["Bava", "Balava", "Kaulava", "Taitila", "Gara", "Vanija", "Vishti"]
VARA = [("Sunday", "Sun"), ("Monday", "Moon"), ("Tuesday", "Mars"), ("Wednesday", "Mercury"),
        ("Thursday", "Jupiter"), ("Friday", "Venus"), ("Saturday", "Saturn")]


def compute_panchang(sun_lon: float, moon_lon: float, weekday_idx: int,
                     moon_nak: str, moon_nak_lord: str) -> Dict:
    """Five limbs from sidereal Sun/Moon longitudes. weekday_idx: 0=Sun … 6=Sat."""
    diff = (moon_lon - sun_lon) % 360
    ti = int(diff // 12)                      # 0..29 across the lunar month
    paksha = "Shukla" if ti < 15 else "Krishna"
    tname = TITHI_NAMES[ti % 15]
    if ti % 15 == 14:
        tname = "Purnima" if paksha == "Shukla" else "Amavasya"
    yi = int(((sun_lon + moon_lon) % 360) // (360 / 27))
    ki = int(diff // 6)                        # 0..59 half-tithis
    if ki == 0:    kname = "Kimstughna"
    elif ki == 57: kname = "Shakuni"
    elif ki == 58: kname = "Chatushpada"
    elif ki == 59: kname = "Naga"
    else:          kname = KARANA_MOVABLE[(ki - 1) % 7]
    vname, vlord = VARA[weekday_idx % 7]
    return {
        "tithi": f"{paksha} {tname}", "tithi_num": ti + 1, "paksha": paksha,
        "tithi_pct": round((diff % 12) / 12 * 100, 1),
        "vara": vname, "vara_lord": vlord,
        "nakshatra": moon_nak, "nakshatra_lord": moon_nak_lord,
        "yoga": YOGA_NAMES[yi % 27], "karana": kname,
    }


# ══════════════════════════════════════════════════════════════════════════════
# CHART GENERATOR
# ══════════════════════════════════════════════════════════════════════════════

def generate_chart(year:int, month:int, day:int, hour:int, minute:int,
                   lat:float, lon:float, tz_offset:float,
                   location:str="", name:str="", gender:str="") -> Dict:
    """Compute a complete Jyotiṣa birth chart (data only, no rendering)."""
    local_dt = datetime(year,month,day,hour,minute,
                        tzinfo=timezone(timedelta(hours=tz_offset)))
    ut_dt    = local_dt.astimezone(timezone.utc)
    hour_ut  = ut_dt.hour + ut_dt.minute/60 + ut_dt.second/3600
    jd       = get_jd(ut_dt.year, ut_dt.month, ut_dt.day, hour_ut)

    lons, ayan, engine = compute_positions(jd, lat, lon)

    planets = {pname: _planet_record(pname, slon) for pname,slon in lons.items()}

    lagna_idx = planets["Ascendant"]["sign_idx"]
    houses    = {h: SIGNS[(lagna_idx+h-1)%12] for h in range(1,13)}
    occupants: Dict[int,List[str]] = {h:[] for h in range(1,13)}
    for pname, pd in planets.items():
        if pname=="Ascendant": continue
        h=(pd["sign_idx"]-lagna_idx)%12+1; pd["house"]=h; occupants[h].append(pname)

    today_dt  = datetime.now(timezone.utc)
    jd_today  = get_jd(today_dt.year, today_dt.month, today_dt.day,
                        today_dt.hour + today_dt.minute/60)
    t_lons, _, _ = compute_positions(jd_today, lat, lon)
    transits  = {pname: _planet_record(pname, slon) for pname,slon in t_lons.items()}

    natal_si  = {p: planets[p]["sign_idx"] for p in planets}
    akv       = compute_ashtakavarga(natal_si)

    d9  = compute_divisional(lons, 9)
    d3  = compute_divisional(lons, 3)
    d10 = compute_divisional(lons, 10)

    varshaphala = compute_varshaphala(
        year, month, day, lons["Sun"], lagna_idx,
        lat, lon, datetime.now().year)

    jaimini = compute_jaimini(lons, lagna_idx)
    chara_dasha = build_chara_dasha(
        {p: planets[p]["sign_idx"] for p in planets if p != "Ascendant"},
        lons, lagna_idx, local_dt.replace(tzinfo=None))

    panchang = compute_panchang(lons["Sun"], lons["Moon"], local_dt.isoweekday() % 7,
                                planets["Moon"]["nakshatra"], planets["Moon"]["nak_lord"])

    ah,am = int(abs(tz_offset)), int(round((abs(tz_offset)%1)*60))
    sgn   = "+" if tz_offset>=0 else "-"

    return {
        "meta": {
            "name": name, "gender": gender,
            "birth":    local_dt.strftime("%d %B %Y  %H:%M"),
            "ut":       ut_dt.strftime("%d %B %Y  %H:%M UTC"),
            "tz":       f"UTC{sgn}{ah:02d}:{am:02d}",
            "location": location, "lat":lat, "lon":lon,
            "jd":       round(jd,5), "ayan": round(ayan,4), "engine": engine,
        },
        "lagna":      planets["Ascendant"]["sign"],
        "lagna_pos":  planets["Ascendant"]["pos"],
        "lagna_idx":  lagna_idx,
        "planets":    planets,
        "houses":     houses,
        "occupants":  occupants,
        "lons":       lons,
        "transits":   transits,
        "transit_date": today_dt.strftime("%d %b %Y"),
        "ashtakavarga": akv,
        "d9":  d9,  "d9_lagna":  d9["Ascendant"],
        "d3":  d3,  "d3_lagna":  d3["Ascendant"],
        "d10": d10, "d10_lagna": d10["Ascendant"],
        "dashas":      build_dashas(lons["Moon"], local_dt.replace(tzinfo=None)),
        "varshaphala": varshaphala,
        "jaimini":     jaimini,
        "chara_dasha": chara_dasha,
        "panchang":    panchang,
    }


EXAMPLE = dict(
    year=1957, month=8, day=24, hour=13, minute=55,
    lat=47.4833, lon=7.7356, tz=1.0,
    location="Liestal, Switzerland",
    name="Example Person", gender="Male",
)
