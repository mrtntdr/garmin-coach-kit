#!/usr/bin/env python3
"""fetch_workout.py [YYYY-MM-DD] [--review]

One-shot data pull for the workout-review skill: today's (or the given date's)
activities with per-lap splits, true HR time-in-zones, and weather (°F→°C fixed)
in the exact JSON shape workout_review.py consumes.

--review additionally runs workout_review.py on the newest run and prints its
metrics digest, so the skill gets everything from a single command.

Output (stdout): one JSON object
  {"date": ..., "activities": [ {activity, splits, hr_zones, weather}, ... ]}
Non-run activities (strength etc.) appear summary-only.
"""
import datetime
import json
import sys

from garmin_client import client, f_to_c, dew_point_c, pace_str

RUN_TYPES = {"running", "trail_running", "track_running", "treadmill_running"}


def compact_activity(a):
    t = (a.get("activityType") or {}).get("typeKey")
    dur = a.get("duration") or 0
    km = (a.get("distance") or 0) / 1000
    return {
        "id": a.get("activityId"),
        "name": a.get("activityName"),
        "type": t,
        "start_time_local": a.get("startTimeLocal"),
        "distance_meters": round(a.get("distance") or 0, 1),
        "duration_seconds": round(dur, 1),
        "moving_duration_seconds": round(a.get("movingDuration") or dur, 1),
        "avg_pace": pace_str(dur / km) if km else None,
        "avg_hr_bpm": a.get("averageHR"),
        "max_hr_bpm": a.get("maxHR"),
        "avg_cadence": a.get("averageRunningCadenceInStepsPerMinute"),
        "avg_ground_contact_time_ms": a.get("avgGroundContactTime"),
        "avg_vertical_oscillation_cm": a.get("avgVerticalOscillation"),
        "avg_stride_length_cm": a.get("avgStrideLength"),
        "avg_power_watts": a.get("avgPower"),
        "training_effect": a.get("aerobicTrainingEffect"),
        "anaerobic_training_effect": a.get("anaerobicTrainingEffect"),
        "training_effect_label": a.get("trainingEffectLabel"),
        "training_load": a.get("activityTrainingLoad"),
        "elevation_gain_meters": a.get("elevationGain"),
        "elevation_loss_meters": a.get("elevationLoss"),
        "calories": a.get("calories"),
    }


def compact_lap(i, l):
    km = (l.get("distance") or 0) / 1000
    dur = l.get("duration") or 0
    return {
        "lap_number": i,
        "distance_meters": round(l.get("distance") or 0, 1),
        "duration_seconds": round(dur, 2),
        "pace": pace_str(dur / km) if km >= 0.1 else None,
        "avg_hr_bpm": l.get("averageHR"),
        "max_hr_bpm": l.get("maxHR"),
        "avg_cadence": l.get("averageRunCadence"),
        "avg_power_watts": l.get("averagePower") or l.get("avgPower"),
        "intensity_type": l.get("intensityType"),
        "elevation_gain_meters": l.get("elevationGain"),
        "elevation_loss_meters": l.get("elevationLoss"),
    }


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    date = args[0] if args else datetime.date.today().isoformat()
    review = "--review" in sys.argv

    g = client()
    acts = g.get_activities_by_date(date, date) or []
    out = {"date": date, "activities": []}

    for a in sorted(acts, key=lambda x: x.get("startTimeLocal") or ""):
        entry = {"activity": compact_activity(a)}
        if entry["activity"]["type"] in RUN_TYPES:
            aid = a["activityId"]
            try:
                laps = (g.get_activity_splits(aid) or {}).get("lapDTOs") or []
                entry["splits"] = {"laps": [compact_lap(i + 1, l) for i, l in enumerate(laps)]}
            except Exception as e:
                entry["splits_error"] = str(e)
            try:
                entry["hr_zones"] = g.get_activity_hr_in_timezones(aid)
            except Exception as e:
                entry["hr_zones_error"] = str(e)
            try:
                w = g.get_activity_weather(aid) or {}
                tc = f_to_c(w.get("temp"))
                entry["weather"] = {
                    "temp_c": tc,
                    "apparent_c": f_to_c(w.get("apparentTemp")),
                    "humidity_pct": w.get("relativeHumidity"),
                    "dew_point_c": dew_point_c(tc, w.get("relativeHumidity")),
                    "wind_kmh": w.get("windSpeed"),
                }
            except Exception as e:
                entry["weather_error"] = str(e)
        out["activities"].append(entry)

    print(json.dumps(out, indent=1, ensure_ascii=False))

    if review:
        from workout_review import compute, render
        runs = [e for e in out["activities"] if e["activity"]["type"] in RUN_TYPES]
        if runs:
            e = runs[-1]
            payload = {"activity": e["activity"], "splits": e.get("splits", {}),
                       "hr_zones": e.get("hr_zones", []),
                       "weather": e.get("weather") or {}, "planned": ""}
            print("\n===== workout_review.py metrics =====")
            print(render(compute(payload)))

if __name__ == "__main__":
    main()
