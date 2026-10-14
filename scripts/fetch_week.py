#!/usr/bin/env python3
"""fetch_week.py [YYYY-MM-DD]

One-shot pull for the weekly-review skill: the plan week (Mon–Sun) containing
the given date (default today) — every activity as a compact line, road/trail
totals, plus the week-over-week trend signals (HRV endpoints, VO2max, race
predictions).

Note: "road" vs "trail" follows the activity TYPE picked on the watch, not the
actual surface.

Output (stdout): one compact JSON object.
"""
import datetime
import json
import sys

from garmin_client import client, pace_str

RUN_TYPES = {"running": "road", "trail_running": "trail",
             "track_running": "road", "treadmill_running": "road"}


def hms(secs):
    secs = round(secs)
    return f"{secs // 3600}:{secs % 3600 // 60:02d}:{secs % 60:02d}"


def main():
    ref = datetime.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else datetime.date.today()
    mon = ref - datetime.timedelta(days=ref.weekday())
    sun = mon + datetime.timedelta(days=6)
    g = client()
    errors = {}
    out = {"week": f"{mon} .. {sun}", "errors": errors}

    acts = g.get_activities_by_date(mon.isoformat(), sun.isoformat()) or []
    rows, road, trail = [], 0.0, 0.0
    for a in sorted(acts, key=lambda x: x.get("startTimeLocal") or ""):
        t = (a.get("activityType") or {}).get("typeKey")
        km = round((a.get("distance") or 0) / 1000, 2)
        dur = a.get("duration") or 0
        kind = RUN_TYPES.get(t)
        if kind == "road":
            road += km
        elif kind == "trail":
            trail += km
        rows.append({
            "date": (a.get("startTimeLocal") or "")[:10],
            "name": a.get("activityName"),
            "type": t,
            "km": km if kind else None,
            "duration_min": round(dur / 60, 1),
            "pace": pace_str(dur / km) if kind and km else None,
            "avg_hr": a.get("averageHR"), "max_hr": a.get("maxHR"),
            "te": round(a["aerobicTrainingEffect"], 1) if a.get("aerobicTrainingEffect") else None,
            "load": round(a.get("activityTrainingLoad") or 0),
            "elev_gain": round(a.get("elevationGain") or 0),
        })
    out["activities"] = rows
    out["totals"] = {"road_km": round(road, 1), "trail_km": round(trail, 1),
                     "total_km": round(road + trail, 1), "runs": sum(1 for r in rows if r["km"])}

    def hrv_endpoints():
        pts = {}
        for d in (mon, sun):
            s = (g.get_hrv_data(d.isoformat()) or {}).get("hrvSummary") or {}
            pts[d.isoformat()] = {"weekly_avg": s.get("weeklyAvg"), "status": s.get("status")}
        return pts
    try:
        out["hrv"] = hrv_endpoints()
    except Exception as e:
        errors["hrv"] = str(e)

    try:
        m = g.get_max_metrics(sun.isoformat()) or []
        gen = (m[0] or {}).get("generic") if m else {}
        out["vo2max"] = (gen or {}).get("vo2MaxPreciseValue") or (gen or {}).get("vo2MaxValue")
    except Exception as e:
        errors["vo2max"] = str(e)

    try:
        r = g.get_race_predictions()
        rec = r[-1] if isinstance(r, list) and r else (r if isinstance(r, dict) else {})
        # 5K/10K predictions are usually close to real races; the marathon figure is
        # an extrapolation over two doublings, so don't steer by it
        out["race_prediction"] = {k: hms(rec.get(f)) for k, f in
                                  (("5k", "time5K"), ("10k", "time10K"),
                                   ("half", "timeHalfMarathon"), ("marathon", "timeMarathon"))
                                  if rec.get(f)}
    except Exception as e:
        errors["race_prediction"] = str(e)

    print(json.dumps(out, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
