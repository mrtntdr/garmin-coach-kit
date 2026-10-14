#!/usr/bin/env python3
"""fetch_readiness.py [YYYY-MM-DD] [--hrv-days N]

One-shot morning-readiness pull for the morning-plan skill: Garmin training
readiness, HRV trend (last 7 nights by default), last night's sleep, body
battery, RHR, morning weight (today + 7-day avg) — plus a compact hourly forecast
for the configured location (Open-Meteo, 06–21), so the skill needs no separate
WebFetch.

HRV and forecast rows are packed as one short string each (decoded by the
output's "_legend" key) to keep the token cost of a morning briefing low.

Output (stdout): one compact JSON object.
"""
import datetime
import json
import sys
import urllib.request

from config import LOCATION
from garmin_client import client, compass, heat_stress

OPEN_METEO = ("https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
              "&hourly=temperature_2m,apparent_temperature,relative_humidity_2m,"
              "precipitation_probability,precipitation,wind_speed_10m,wind_direction_10m,"
              "uv_index&timezone={tz}&start_date={date}&end_date={date}")


def safe(fn, label, errors):
    try:
        return fn()
    except Exception as e:
        errors[label] = str(e)
        return None


def parse_args(argv):
    args, hrv_days = list(argv), 7
    if "--hrv-days" in args:
        k = args.index("--hrv-days")
        hrv_days = int(args[k + 1])
        del args[k:k + 2]
    date = args[0] if args else datetime.date.today().isoformat()
    datetime.date.fromisoformat(date)          # fail fast on a bad date
    return date, hrv_days


def hrv_row(d, s):
    """'MM-DD wk<weekly> n<nightly> hi<5-min high> [low-high] STATUS'."""
    b = s.get("baseline") or {}
    return (f'{d[5:]} wk{s.get("weeklyAvg")} n{s.get("lastNightAvg")} '
            f'hi{s.get("lastNight5MinHigh")} '
            f'[{b.get("balancedLow")}-{b.get("balancedUpper")}] {s.get("status")}')


def forecast_row(hour, temp, feels, rh, rain_p, rain_mm, wind, wind_dir, uv):
    """'HH temp/feels dew<n> <level> wind<n><FROM> rain<p>%/<mm> uv<n> (note)'."""
    hs = heat_stress(temp, rh, uv, wind) or {}
    row = (f'{hour:02d} {temp:.0f}/{feels:.0f} dew{hs.get("dew_c") or 0:.0f} '
           f'{hs.get("level")} wind{wind:.0f}{compass(wind_dir)} '
           f'rain{rain_p}%/{rain_mm:g} uv{uv:g}')
    return row + (f' ({hs["note"]})' if hs.get("note") else "")


def main():
    date, hrv_days = parse_args(sys.argv[1:])
    g = client()
    errors = {}
    out = {"date": date, "errors": errors, "_legend": {
        "hrv_trend": "MM-DD wk<weekly avg> n<nightly avg> hi<5-min high> [baseline] STATUS"
                     " (judge the night by n, not hi)",
        "forecast": "HH temp/feels°C dew<°C> <heat level> wind<km/h><blowing FROM>"
                    " rain<prob>%/<mm> uv<n> (+ heat note if any)"}}

    # Garmin readiness score (often n/a on watches without it — that's normal)
    tr = safe(lambda: g.get_training_readiness(date), "training_readiness", errors)
    if isinstance(tr, list):
        tr = tr[0] if tr else None
    if tr:
        out["training_readiness"] = {k: tr.get(k) for k in
                                     ("score", "level", "feedbackShort", "feedbackLong")}

    def hrv_trend():
        rows = []
        for k in range(hrv_days - 1, -1, -1):
            d = (datetime.date.fromisoformat(date) - datetime.timedelta(days=k)).isoformat()
            s = (g.get_hrv_data(d) or {}).get("hrvSummary") or {}
            if s.get("weeklyAvg") is None and s.get("lastNight5MinHigh") is None:
                continue
            rows.append(hrv_row(d, s))
        return rows
    out["hrv_trend"] = safe(hrv_trend, "hrv", errors)

    def sleep():
        raw = g.get_sleep_data(date) or {}
        dto = raw.get("dailySleepDTO") or {}
        secs = dto.get("sleepTimeSeconds") or 0
        return {
            "hours": round(secs / 3600, 2),
            "score": ((dto.get("sleepScores") or {}).get("overall") or {}).get("value"),
            "deep_pct": round(100 * (dto.get("deepSleepSeconds") or 0) / secs, 1) if secs else None,
            "rem_pct": round(100 * (dto.get("remSleepSeconds") or 0) / secs, 1) if secs else None,
            "awake_count": dto.get("awakeCount"),
            # top-level in the payload, NOT inside dailySleepDTO
            "avg_overnight_hrv": raw.get("avgOvernightHrv"),
            "avg_sleep_stress": dto.get("avgSleepStress"),
        }
    out["sleep"] = safe(sleep, "sleep", errors)

    def battery():
        bb = g.get_body_battery(date, date) or []
        day = bb[0] if bb else {}
        return {"charged": day.get("charged"), "drained": day.get("drained")}
    out["body_battery"] = safe(battery, "body_battery", errors)

    # Resting HR — PRELIMINARY early in the morning (Garmin finalizes it later), so
    # report the 7-day avg + today's min HR as well.
    def rhr():
        r = g.get_rhr_day(date)
        vals = (((r or {}).get("allMetrics") or {}).get("metricsMap") or {}) \
            .get("WELLNESS_RESTING_HEART_RATE") or []
        day = vals[0].get("value") if vals else None
        st = {}
        try:
            st = g.get_stats(date) or {}
        except Exception:
            pass
        min_hr, max_hr = st.get("minHeartRate"), st.get("maxHeartRate")
        # a full day maxes out well above ~120; if not, the record is still partial
        preliminary = bool(day is None or (max_hr and max_hr < 120))
        return {"today": day, "seven_day_avg": st.get("lastSevenDaysAvgRestingHeartRate"),
                "day_min_hr": min_hr, "preliminary": preliminary,
                # min HR above RHR is impossible: the day hasn't finished syncing
                "partial_sync": bool(day and min_hr and min_hr > day) or None}
    out["rhr"] = safe(rhr, "rhr", errors)

    # Morning weight: today's entry (null = not logged yet) + the 7-day average,
    # which is what matters (single days swing 1–2 kg on water and glycogen).
    def weight():
        start = (datetime.date.fromisoformat(date) - datetime.timedelta(days=6)).isoformat()
        days = (g.get_weigh_ins(start, date) or {}).get("dailyWeightSummaries") or []
        kg = {d["summaryDate"]: round(d["latestWeight"]["weight"] / 1000, 1)
              for d in days if (d.get("latestWeight") or {}).get("weight")}
        return {"today": kg.get(date),
                "seven_day_avg": round(sum(kg.values()) / len(kg), 1) if kg else None,
                "n_days": len(kg)}
    out["weight"] = safe(weight, "weight", errors)

    def weather():
        if LOCATION.get("lat") is None or LOCATION.get("lon") is None:
            return None
        url = OPEN_METEO.format(lat=LOCATION["lat"], lon=LOCATION["lon"], date=date,
                                tz=LOCATION.get("timezone") or "auto")
        with urllib.request.urlopen(url, timeout=20) as r:
            h = json.load(r)["hourly"]
        rows = []
        for i, stamp in enumerate(h["time"]):
            hour = int(stamp[11:13])
            if 6 <= hour <= 21 and h["temperature_2m"][i] is not None:
                rows.append(forecast_row(
                    hour, h["temperature_2m"][i], h["apparent_temperature"][i],
                    h["relative_humidity_2m"][i], h["precipitation_probability"][i],
                    h["precipitation"][i] or 0, h["wind_speed_10m"][i] or 0,
                    h["wind_direction_10m"][i], h["uv_index"][i] or 0))
        return rows
    out["forecast"] = safe(weather, "forecast", errors)
    out["forecast_location"] = LOCATION.get("name")

    print(json.dumps(out, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
