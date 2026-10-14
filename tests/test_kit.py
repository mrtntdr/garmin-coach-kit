"""Golden-value tests for the kit. No Garmin login or network needed.

Every function here fails SILENTLY: a wrong decoupling or pace figure is still a
plausible-looking number. Run after touching any formula:

    python3 tests/test_kit.py          (no pytest needed)
    python3 -m pytest tests/
"""
import datetime
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("ATHLETE_CONFIG", os.path.join(ROOT, "athlete.example.json"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from config import LT1, LT2                                       # noqa: E402
from garmin_client import compass, dew_point_c, f_to_c, heat_stress  # noqa: E402
import fetch_readiness as fr                                      # noqa: E402
import fetch_week as fw                                           # noqa: E402
import load                                                       # noqa: E402
import plan_today as pt                                           # noqa: E402
import workout_review as wr                                       # noqa: E402


def close(a, b, tol):
    return abs(a - b) <= tol


# ───────────────────────── weather ─────────────────────────
def test_f_to_c_handles_the_garmin_quirk():
    # get_activity_weather puts °F in a field named temperature_celsius
    assert f_to_c(66) == 18.9
    assert f_to_c(None) is None


def test_dew_point():
    assert close(dew_point_c(20.0, 100), 20.0, 0.1)
    assert close(dew_point_c(30.0, 50), 18.4, 0.2)
    assert dew_point_c(10, 0) is None


def test_heat_stress_is_driven_by_dew_point():
    assert heat_stress(24, 35)["level"] == "good"       # warm but dry
    assert heat_stress(22, 95)["level"] in ("hard", "severe")


def test_compass_is_direction_wind_blows_from():
    assert compass(0) == "N" and compass(359) == "N"
    assert compass(135) == "SE" and compass(270) == "W"
    assert compass(None) == ""


def test_forecast_row_is_compact_and_has_wind_direction():
    row = fr.forecast_row(18, 10.4, 7.6, 80, 5, 0.0, 13.2, 140, 0.15)
    assert row.startswith("18 10/8 dew7 good wind13SE rain5%/0 uv0.15"), row


def test_hrv_row():
    s = {"weeklyAvg": 53, "lastNightAvg": 69, "lastNight5MinHigh": 111,
         "baseline": {"balancedLow": 44, "balancedUpper": 59}, "status": "BALANCED"}
    assert fr.hrv_row("2026-10-14", s) == "10-14 wk53 n69 hi111 [44-59] BALANCED"


def test_readiness_args():
    assert fr.parse_args(["2026-10-14", "--hrv-days", "14"]) == ("2026-10-14", 14)
    assert fr.parse_args([])[1] == 7


# ───────────────────────── metrics ─────────────────────────
def laps_from(rows):
    """rows: (km, seconds, hr) → the fetch_workout lap shape."""
    return {"laps": [{"distance_meters": km * 1000, "duration_seconds": s, "avg_hr_bpm": hr}
                     for km, s, hr in rows]}


def test_drift_pace_is_time_over_distance_not_mean_lap_duration():
    # 4 × 1 km @ 5:30, then two partial laps at the same pace. Mean lap duration
    # would make the second half look much faster than it is.
    rows = [(1, 330, 140)] * 4 + [(0.45, 148.5, 142), (0.56, 184.8, 142)]
    laps = wr.normalize_laps({"splits": laps_from(rows)})
    d = wr.drift(laps)
    assert d["first_half_pace"] == 330 and d["second_half_pace"] == 330, d


def test_decoupling_weights_a_short_final_lap_by_distance():
    # Steady 10 km at constant speed and HR + a 0.38 km lap at a slower, harder
    # pace. Distance-weighted, it barely moves decoupling; a plain lap mean would
    # count it as a full kilometre.
    rows = [(1, 300, 150)] * 10 + [(0.38, 130, 156)]
    laps = wr.normalize_laps({"splits": laps_from(rows)})
    dec, e1, e2 = wr.decoupling_from_laps(laps)
    assert 0 < dec < 3, dec


def test_decoupling_zero_when_steady():
    laps = wr.normalize_laps({"splits": laps_from([(1, 300, 150)] * 12)})
    assert wr.decoupling_from_laps(laps)[0] == 0.0


def test_zone_split_does_not_invent_time_above_session_max():
    # Easy run that never exceeded LT1 - 1, but whose Garmin zone straddles LT1
    zones = [{"zoneLowBoundary": LT1 - 30, "secsInZone": 600},
             {"zoneLowBoundary": LT1 - 8, "secsInZone": 2400},
             {"zoneLowBoundary": LT2, "secsInZone": 0}]
    inp = {"activity": {"max_hr_bpm": LT1 - 1}, "hr_zones": zones}
    secs, _ = wr.zone_split(inp, [], 3000, LT1 - 10)
    assert secs["moderate"] == 0 and secs["hard"] == 0


def test_compute_survives_missing_fields():
    m = wr.compute({"activity": {"start_time_local": None}})
    assert m["km"] == 0 and m["pace_s_km"] is None
    wr.render(m)                                   # must not raise


def test_weather_accepts_converted_or_raw_garmin():
    a = {"distance_meters": 5000, "moving_duration_seconds": 1500, "avg_hr_bpm": 140}
    assert wr.compute({"activity": a, "weather": {"temp_c": 19}})["temp_c"] == 19
    assert wr.compute({"activity": a, "weather": {"temperature_celsius": 66}})["temp_c"] == 18.9


def test_hms():
    assert fw.hms(2433) == "0:40:33" and fw.hms(10800.4) == "3:00:00"


# ───────────────────────── load ─────────────────────────
def act(day, mins, hr, kind="running", gl=50, te=3.0, ana=0.0, name="Run"):
    return {"startTimeLocal": f"{day} 18:00:00", "duration": mins * 60, "averageHR": hr,
            "activityType": {"typeKey": kind}, "activityTrainingLoad": gl,
            "aerobicTrainingEffect": te, "anaerobicTrainingEffect": ana, "activityName": name}


def test_trimp_banister_and_sex_weighting():
    # athlete.example: hr_rest 50, hr_max 190. 60 min at HRR 0.5 (HR 120):
    # male 60 × 0.5 × 0.64 × e^0.96 ≈ 50.1
    assert close(load.trimp(3600, 120), 50.1, 0.1)
    assert load.trimp(3600, None) == 0 and load.trimp(0, 140) == 0
    a, b = 0.86, 1.67                       # female weighting is higher at low HRR
    assert 60 * 0.5 * a * load.math.exp(b * 0.5) > load.trimp(3600, 120)


def test_acwr_is_7d_over_28d_quarter():
    end = datetime.date(2026, 10, 14)
    # 4 identical weeks → ratio 1.0 for both models
    acts = [act((end - datetime.timedelta(days=d)).isoformat(), 50, 145) for d in range(0, 28, 2)]
    s = load.summarize(acts, end)
    assert close(s["trimp_acwr"], 1.0, 0.15) and close(s["garmin_acwr"], 1.0, 0.15), s
    # strength counts for Garmin load but not TRIMP
    s2 = load.summarize(acts + [act(end.isoformat(), 45, 110, "strength_training", gl=300)], end)
    assert s2["trimp_7d"] == s["trimp_7d"] and s2["garmin_load_7d"] == s["garmin_load_7d"] + 300
    assert load.summarize([], end)["trimp_acwr"] is None


def test_last_hard_day():
    end = datetime.date(2026, 10, 14)
    acts = [act("2026-10-08", 40, 160, ana=3.2, name="Intervals"),
            act("2026-10-11", 100, 145, name="Long"),
            act("2026-10-13", 45, 140, ana=1.9, name="Easy + strides")]   # NOT hard
    h = load.summarize(acts, end)["last_hard"]
    assert h["date"] == "2026-10-11" and h["days_ago"] == 3 and h["why"] == "100 min", h
    assert load.is_hard(act("2026-10-08", 40, 160, ana=3.2)) == "anaerobic TE 3.2"
    assert load.is_hard(act("2026-10-08", 50, 165, te=4.3)) == "aerobic TE 4.3"


def test_week_trimp_vs_prior_four():
    mon = datetime.date(2026, 10, 12)
    acts = [act((mon - datetime.timedelta(weeks=k)).isoformat(), 60, 145) for k in range(1, 5)]
    acts += [act(mon.isoformat(), 60, 145), act((mon + datetime.timedelta(days=2)).isoformat(), 60, 145)]
    w = load.week_trimp(acts, mon)
    assert w["week_vs_prior_4wk"] == 2.0, w


# ───────────────────────── plan extract ─────────────────────────
def test_plan_extract_today_tomorrow_and_week():
    lines = open(os.path.join(ROOT, "examples", "plan.example.md")).read().splitlines()
    out = pt.extract(lines, datetime.date(2026, 10, 11))
    assert sum(1 for l in out if l.startswith("| 2026-")) == 2       # Sun + Mon
    assert sum(1 for l in out if l.startswith("| date")) == 2        # both week headers
    wk = pt.extract(lines, datetime.date(2026, 10, 14), week=True)
    assert sum(1 for l in wk if l.startswith("| 2026-")) == 7
    assert pt.extract(lines, datetime.date(2027, 1, 1)) == []


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  ok   {name}")
            except Exception as e:
                fails += 1
                print(f"  FAIL {name}: {e!r}")
    n = sum(1 for k in globals() if k.startswith("test_"))
    print(f"\n{n - fails}/{n} passed")
    sys.exit(1 if fails else 0)
