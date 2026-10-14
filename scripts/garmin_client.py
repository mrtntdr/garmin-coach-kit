"""Shared Garmin auth + helpers for the fetch scripts.

Token-only by design: resumes the cached session at ~/.garminconnect (written by
login.py). No credentials, no MFA — if the
token is missing/expired it exits with instructions instead of prompting, so these
scripts are always safe to run non-interactively (e.g. from Claude Code skills).
"""
import math
import os
import sys

TOKENSTORE = os.environ.get("GARMINTOKENS", os.path.expanduser("~/.garminconnect"))


def client():
    from garminconnect import Garmin
    g = Garmin()
    try:
        g.login(TOKENSTORE)
        return g
    except Exception as e:
        sys.exit(f"Garmin token resume failed ({e}).\n"
                 f"Refresh it once interactively: python3 scripts/login.py "
                 f"(may prompt MFA, re-caches the token).")


def f_to_c(f):
    """Garmin weather reports °F in fields named like Celsius — convert."""
    return None if f is None else round((f - 32) * 5 / 9, 1)


def dew_point_c(temp_c, rh):
    if temp_c is None or not rh:
        return None
    gam = math.log(rh / 100) + 17.625 * temp_c / (243.04 + temp_c)
    return round(243.04 * gam / (17.625 - gam), 1)


def heat_stress(temp_c, rh, uv=None, wind_kmh=None):
    """Running heat-stress estimate from forecast fields.

    Returns {dew_c, wbgt_est, level, note}.

    Rationale (WBGT = 0.7*wet-bulb + 0.2*globe + 0.1*dry-bulb): humidity carries ~3.5x
    the weight of solar load, and plain air temperature is the SMALLEST term — which is
    why "it's only 24C" misleads. Dew point is used (not RH) because RH is
    temperature-dependent; dew point is an absolute measure of moisture.

    `wbgt_est` is the shade/no-solar WBGT approximation (Australian BoM form) plus a
    crude solar bump from UV. It is an ESTIMATE, not a measured globe temperature.
    """
    if temp_c is None or rh is None:
        return None
    dew = dew_point_c(temp_c, rh)
    # BoM shade approximation: WBGT ~ 0.567*Ta + 0.393*e + 3.94, e = vapour pressure (hPa)
    e = (rh / 100) * 6.105 * math.exp(17.27 * temp_c / (237.7 + temp_c))
    wbgt = 0.567 * temp_c + 0.393 * e + 3.94
    if uv:                      # crude radiant-load bump for direct sun
        wbgt += min(uv, 8) * 0.4
    # Level driven by dew point (the dominant term), escalated for sun / dead air.
    steps = ["good", "fair", "moderate", "hard", "severe"]
    i = 0 if dew < 12 else 1 if dew < 16 else 2 if dew < 18 else 3 if dew < 21 else 4
    notes = []
    if uv is not None and uv >= 4:
        i += 1; notes.append("strong sun")
    if temp_c >= 30:            # dry heat still loads you even at low dew point
        i += 2; notes.append("very hot air")
    elif temp_c >= 26:
        i += 1; notes.append("hot air")
    if wind_kmh is not None and wind_kmh < 5 and dew >= 14:
        i += 1; notes.append("still air (no evaporative help)")
    i = min(i, 4)
    return {"dew_c": dew, "wbgt_est": round(wbgt, 1), "level": steps[i],
            "note": ", ".join(notes) or None}


def compass(deg):
    """8-point compass for the direction the wind blows FROM ('' if unknown)."""
    if deg is None:
        return ""
    return "N NE E SE S SW W NW".split()[round(deg / 45) % 8]


def pace_str(sec_per_km):
    if not sec_per_km:
        return None
    return f"{int(sec_per_km // 60)}:{int(sec_per_km % 60):02d}"
