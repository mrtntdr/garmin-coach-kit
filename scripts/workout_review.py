#!/usr/bin/env python3
"""
workout_review.py — rich post-workout metrics for ONE run, normally called via
`fetch_workout.py --review` (the `workout-review` skill).

WHY THIS EXISTS
  Classifying a whole run by its AVERAGE heart rate (what most 80/20 trackers do)
  misleads: a threshold session (easy warm-up + recoveries + hard reps) averages out to
  "easy". This script computes a TRUE time-in-zone 80/20 from per-zone seconds (or
  the HR stream), so the reps actually land in the moderate/hard buckets. It also
  computes TRIMP, aerobic decoupling, efficiency factor (EF), and a per-km drift
  table — for a single activity, right after it's done.

USAGE
  python3 workout_review.py workout.json          # compute from a gathered file
  python3 workout_review.py --json workout.json   # same
  python3 workout_review.py --out metrics.json ...# also write computed metrics JSON
  python3 workout_review.py --demo                # synthetic threshold session (shows the 80/20 fix)
  python3 workout_review.py --demo long           # synthetic long run (decoupling + per-km)

INPUT FILE  (any subset — more data = more metrics)
  {
    "activity":  { ...get_activity result... },          # dist/time/hr/power/TE
    "splits":    { "laps": [ ...get_activity_splits... ] },
    "hr_zones":  [ ...get_activity_hr_in_timezones... ], # secsInZone + zoneLowBoundary
    "hr_stream": [ {"t": secs, "hr": bpm}, ... ],         # optional; most accurate 80/20
    "weather":   {"temp_c": .., "humidity_pct": ..}      # or raw get_activity_weather
                                                         # (NB its temperature_celsius is °F)
    "planned":   "free-text planned session"              # optional, echoed
  }
  km_splits shorthand is also accepted: {"km_splits": {"pace_s": [...], "hr": [...]}}.

80/20 SOURCE PRIORITY (best → fallback)
  hr_stream  >  hr_zones (true secs-in-zone)  >  per-lap (dur × band)  >  whole-run avg HR
Zone model (athlete anchors): easy <LT1 · moderate LT1–LT2 · hard >LT2 (values in athlete.json).
"""

import argparse, json, math, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import LT1, LT2, HR_MAX, HR_REST
from garmin_client import f_to_c, dew_point_c


def trimp(dur_s, avg_hr):
    """Banister TRIMP (male weighting 0.64·e^1.92x)."""
    hrr = (avg_hr - HR_REST) / (HR_MAX - HR_REST)
    return (dur_s / 60) * hrr * 0.64 * math.exp(1.92 * hrr)


def halves(laps):
    """Split laps into first/second half by DISTANCE (a lap goes to the half its
    midpoint falls in). Falls back to lap count when distances are missing."""
    total = sum(L.get("dist") or 0 for L in laps)
    fh, sh, cum = [], [], 0.0
    for L in laps:
        d = L.get("dist") or 0
        (fh if total and cum + d / 2 < total / 2 else sh).append(L)
        cum += d
    if not total or not fh or not sh:
        h = len(laps) // 2
        fh, sh = laps[:h], laps[h:]
    return fh, sh


def ef_of(laps):
    """EF = speed (m/s) / time-weighted HR × 1000, over a set of laps."""
    t = sum(L["dur"] for L in laps)
    d = sum(L.get("dist") or 0 for L in laps)
    hr = sum(L["hr"] * L["dur"] for L in laps) / t if t else 0
    return (d / t) / hr * 1000 if t and hr else None


def decoupling_from_laps(laps):
    """Aerobic decoupling %: drop the warm-up lap, split the rest into halves by
    distance, decoupling = (EF1 - EF2) / EF1 × 100.

    Halves are distance-weighted and each half's EF is total distance / total time
    over time-weighted HR, so a short final lap (e.g. 0.38 km) counts as 0.38 km,
    not as a full lap. A plain mean of lap speeds and HRs over-weights it."""
    fh, sh = halves(laps[1:])
    e1, e2 = ef_of(fh), ef_of(sh)
    return round((e1 - e2) / e1 * 100, 1), e1, e2


def fmt_pace(sec):
    m, x = divmod(int(round(sec)), 60)
    return f"{m}:{x:02d}"


def fmt_hms(sec):
    h = int(sec // 3600); m = int((sec % 3600) // 60); s = int(sec % 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


# ───────────────────────── helpers ─────────────────────────
def band(hr):
    """easy / moderate / hard by the athlete's LT1/LT2."""
    return "easy" if hr < LT1 else "moderate" if hr < LT2 else "hard"

def pct(parts):
    tot = sum(parts.values()) or 1
    return {k: round(v / tot * 100) for k, v in parts.items()}


def normalize_laps(inp):
    """Return [{dur, hr, speed, power, cad, intensity}] from either the Garmin
    get_activity_splits shape or the km_splits shorthand. [] if none."""
    laps = []
    sp = inp.get("splits") or {}
    if sp.get("laps"):
        for L in sp["laps"]:
            dur = L.get("moving_duration_seconds") or L.get("duration_seconds") or 0
            spd = L.get("avg_speed_mps")
            if not spd and L.get("distance_meters") and dur:
                spd = L["distance_meters"] / dur
            dist = L.get("distance_meters") or (spd * dur if spd and dur else 0)
            laps.append({"dur": dur, "dist": dist, "hr": L.get("avg_hr_bpm") or 0, "speed": spd,
                         "power": L.get("avg_power_watts"), "cad": L.get("avg_cadence"),
                         "intensity": (L.get("intensity_type") or "").upper()})
    elif inp.get("km_splits"):
        ks = inp["km_splits"]
        pace_s, hrs = ks.get("pace_s", []), ks.get("hr", [])
        for p, h in zip(pace_s, hrs):
            laps.append({"dur": p, "dist": 1000 if p else 0, "hr": h,
                         "speed": 1000 / p if p else None,
                         "power": None, "cad": None, "intensity": "INTERVAL"})
    return laps


# ───────────────────── 80/20 time-in-zone ─────────────────────
def zone_split(inp, laps, moving_s, avg_hr):
    """Return (seconds_by_band, method_str). Tries the most accurate source first."""
    secs = {"easy": 0.0, "moderate": 0.0, "hard": 0.0}

    # 1) full HR stream — most accurate
    stream = inp.get("hr_stream")
    if stream:
        prev_t = None
        for i, s in enumerate(stream):
            hr = s["hr"] if isinstance(s, dict) else s
            t = s.get("t") if isinstance(s, dict) else i
            dt = (t - prev_t) if (prev_t is not None and t is not None) else 1
            prev_t = t
            if hr:
                secs[band(hr)] += dt
        return secs, "HR stream (per-sample)"

    # 2) Garmin time-in-zone — split each zone ACROSS the athlete's LT boundaries.
    #
    # Classifying a whole zone by its midpoint misreports whenever a Garmin zone
    # straddles LT1 or LT2 (e.g. an easy run capped just under LT1 gets booked as
    # "moderate" because its Garmin zone's midpoint sits above LT1).
    #
    # Two corrections: (a) split a straddling zone proportionally across the boundary,
    # (b) clamp the top of the highest occupied zone to the session max HR — you cannot
    # have spent time above the maximum you actually reached.
    hz = inp.get("hr_zones")
    if hz:
        zs = sorted(hz, key=lambda z: z["zoneLowBoundary"])
        act = inp.get("activity") or {}
        cap = act.get("max_hr_bpm") or max((L["hr"] for L in laps), default=0) or HR_MAX
        for i, z in enumerate(zs):
            sec = z.get("secsInZone", 0) or 0
            if sec <= 0:
                continue
            lo = z["zoneLowBoundary"]
            hi = zs[i + 1]["zoneLowBoundary"] if i + 1 < len(zs) else HR_MAX
            hi = min(hi, max(cap, lo + 1))          # no time above the session max
            edges = sorted({lo, hi} | {b for b in (LT1, LT2) if lo < b < hi})
            span = hi - lo
            for a_, b_ in zip(edges, edges[1:]):
                secs[band((a_ + b_) / 2)] += sec * (b_ - a_) / span
        return secs, "Garmin time-in-zone (true secs, zones→LT bands)"

    # 3) per-lap: weight each lap's duration by the lap's avg-HR band
    if laps and any(L["hr"] for L in laps):
        for L in laps:
            if L["hr"]:
                secs[band(L["hr"])] += L["dur"]
        return secs, "per-lap (lap avg-HR × duration)"

    # 4) whole-run average HR — the coarse method (last resort)
    secs[band(avg_hr)] += moving_s
    return secs, "whole-run avg HR (coarse)"


def drift(laps):
    """First- vs second-half HR and pace, split by DISTANCE, weighted by time.

    Pace is total time / total distance for each half, NOT the mean lap duration:
    that is only pace/km when every lap is exactly 1 km, and a run with partial laps
    (auto-lap remainders, manual laps for strides) reads minutes too fast.
    HR is time-weighted for the same reason: a short lap must not count as a full one.
    """
    fh, sh = halves(laps)

    def hr(xs):
        t = sum(L["dur"] for L in xs)
        return round(sum(L["hr"] * L["dur"] for L in xs) / t) if t else None

    def pace(xs):
        d = sum(L.get("dist") or 0 for L in xs)
        return round(sum(L["dur"] for L in xs) / d * 1000) if d else None

    return {"first_half_hr": hr(fh), "second_half_hr": hr(sh),
            "first_half_pace": pace(fh), "second_half_pace": pace(sh)}


# ─────────────────────── main compute ───────────────────────
def compute(inp):
    a = inp.get("activity", {}) or {}
    laps = normalize_laps(inp)

    dist_m = a.get("distance_meters") or sum(L.get("dist") or 0 for L in laps)
    moving_s = a.get("moving_duration_seconds") or a.get("duration_seconds") \
        or sum(L["dur"] for L in laps)
    avg_hr = a.get("avg_hr_bpm") or (round(sum(L["hr"] * L["dur"] for L in laps) /
                                           sum(L["dur"] for L in laps)) if laps else 0)
    max_hr = a.get("max_hr_bpm") or (max((L["hr"] for L in laps), default=0))
    km = dist_m / 1000

    out = {"name": a.get("name") or inp.get("name") or "Run",
           "date": (a.get("start_time_local") or "")[:10] or inp.get("date", ""),
           "km": round(km, 2), "moving_s": round(moving_s),
           "avg_hr": avg_hr, "max_hr": max_hr,
           "pace_s_km": round(moving_s / km) if km else None,
           "elev_gain": a.get("elevation_gain_meters"),
           "training_effect": a.get("training_effect"),
           "training_load": a.get("training_load"),
           "planned": inp.get("planned")}

    # TRIMP — per-lap sum if we have laps (more accurate), else whole-run
    if laps and all(L["hr"] for L in laps):
        out["trimp"] = round(sum(trimp(L["dur"], L["hr"]) for L in laps))
        out["trimp_method"] = "per-lap sum"
    elif avg_hr:
        out["trimp"] = round(trimp(moving_s, avg_hr))
        out["trimp_method"] = "whole-run"

    # Efficiency factor (speed m/s ÷ HR × 1000)
    if avg_hr and moving_s:
        out["ef"] = round((dist_m / moving_s) / avg_hr * 1000, 2)

    # TRUE 80/20 time-in-zone
    secs, method = zone_split(inp, laps, moving_s, avg_hr)
    out["zone_secs"] = {k: round(v) for k, v in secs.items()}
    out["zone_pct"] = pct(secs)
    out["zone_method"] = method
    # what the coarse avg-HR method *would* have said, for contrast
    out["zone_pct_avghr_method"] = {band(avg_hr): 100, **{b: 0 for b in
                                    ("easy", "moderate", "hard") if b != band(avg_hr)}}

    # Aerobic decoupling — only meaningful on steady runs ≥ ~50 min
    steady = moving_s >= 3000 and out["zone_pct"].get("hard", 0) < 15 and len(laps) >= 8
    if steady and all(L.get("dist") and L["hr"] for L in laps):
        dec, e1, e2 = decoupling_from_laps(laps)
        out["decoupling_pct"] = dec
        out["ef_first_half"], out["ef_second_half"] = round(e1, 2), round(e2, 2)
    else:
        out["decoupling_pct"] = None
        out["decoupling_note"] = "n/a (interval/short session — decoupling needs a steady run ≥~50 min)"

    # HR/pace drift, first vs second half
    if laps and len(laps) >= 4 and all(L["hr"] for L in laps):
        out["drift"] = drift(laps)

    # Weather (Garmin returns °F in temperature_celsius; no dew point)
    w = inp.get("weather") or {}
    tc = w.get("temp_c")
    if tc is None and w.get("temperature_celsius") is not None:
        tc = f_to_c(w["temperature_celsius"])
    if tc is not None:
        out["temp_c"] = tc
        rh = w.get("humidity_pct") or w.get("relativeHumidity") or w.get("humidity_percent")
        if rh:
            out["humidity_pct"] = rh
            out["dew_point_c"] = dew_point_c(tc, rh)
    return out


# ─────────────────────── pretty print ───────────────────────
def render(m):
    L = []
    L.append(f"=== {m['date']}  {m['name']} ===")
    pace = f"{fmt_pace(m['pace_s_km'])}/km" if m.get("pace_s_km") else "pace n/a"
    line = (f"{m['km']} km · {fmt_hms(m['moving_s'])} · {pace} · "
            f"HR {round(m['avg_hr'] or 0)}/{round(m['max_hr'] or 0)}")
    if m.get("elev_gain") is not None: line += f" · +{round(m['elev_gain'])} m"
    L.append(line)
    if m.get("temp_c") is not None:
        wx = f"weather {m['temp_c']}°C"
        if m.get("dew_point_c") is not None: wx += f" · dew {m['dew_point_c']}°C · RH {m['humidity_pct']}%"
        L.append(wx)
    if m.get("planned"): L.append(f"planned: {m['planned']}")
    L.append("")

    if m.get("trimp"): L.append(f"TRIMP {m['trimp']} ({m['trimp_method']})" +
                                (f" · TE {round(m['training_effect'], 1)}" if m.get("training_effect") else "") +
                                (f" · load {round(m['training_load'])}" if m.get("training_load") else ""))
    if m.get("ef"): L.append(f"Efficiency factor (EF) {m['ef']}")
    L.append("")

    z, zp = m["zone_secs"], m["zone_pct"]
    L.append(f"TRUE 80/20 — {m['zone_method']}")
    L.append(f"  easy {zp['easy']}%  ·  moderate {zp['moderate']}%  ·  hard {zp['hard']}%")
    L.append(f"  ({fmt_hms(z['easy'])} easy / {fmt_hms(z['moderate'])} mod / {fmt_hms(z['hard'])} hard)")
    old = m["zone_pct_avghr_method"]
    oldband = [b for b in ("easy", "moderate", "hard") if old.get(b) == 100][0]
    if 100 - zp[oldband] >= 10:     # only worth saying when the coarse label misleads
        L.append(f"  (whole-run avg-HR method would call this 100% {oldband} — this is the correction)")
    L.append("")

    if m.get("decoupling_pct") is not None:
        d = m["decoupling_pct"]
        verdict = "excellent (<5%)" if d < 5 else "moderate (5–10%)" if d < 10 else "poor (>10%)"
        L.append(f"Aerobic decoupling {d}%  → {verdict}   (EF {m['ef_first_half']} → {m['ef_second_half']})")
    else:
        L.append(f"Aerobic decoupling: {m.get('decoupling_note','n/a')}")

    if m.get("drift"):
        dft = m["drift"]
        s = f"Drift: HR {dft['first_half_hr']}→{dft['second_half_hr']}"
        if dft.get("first_half_pace") and dft.get("second_half_pace"):
            s += f" · pace {fmt_pace(dft['first_half_pace'])}→{fmt_pace(dft['second_half_pace'])}/km"
        L.append(s)
    return "\n".join(L)


# ─────────────────────── embedded demos ───────────────────────
def demo_input(which):
    """Synthetic sessions — zone boundaries are placed around the configured LT1/LT2."""
    z = [{"zoneNumber": 1, "zoneLowBoundary": LT1 - 35}, {"zoneNumber": 2, "zoneLowBoundary": LT1 - 8},
         {"zoneNumber": 3, "zoneLowBoundary": LT1 + 5}, {"zoneNumber": 4, "zoneLowBoundary": LT2 - 5},
         {"zoneNumber": 5, "zoneLowBoundary": LT2 + 5}]
    if which == "long":
        pace = [330, 328, 326, 327, 325, 329, 326, 324, 327, 325, 323, 326, 328, 330, 327, 325, 329, 331]
        hr = [LT1 - 14 + min(i, 12) // 2 for i in range(len(pace))]
        for zz, sec in zip(z, (600, 5200, 100, 0, 0)):
            zz["secsInZone"] = sec
        return {"activity": {"name": "Long Run (demo)", "start_time_local": "2026-01-01T09:00:00",
                             "distance_meters": 18000, "moving_duration_seconds": sum(pace),
                             "avg_hr_bpm": round(sum(hr) / len(hr)), "max_hr_bpm": max(hr) + 3,
                             "elevation_gain_meters": 120},
                "km_splits": {"pace_s": pace, "hr": hr}, "hr_zones": z,
                "weather": {"temp_c": 14, "humidity_pct": 70},
                "planned": "Long run 18 km easy"}
    for zz, sec in zip(z, (700, 900, 500, 800, 0)):
        zz["secsInZone"] = sec
    return {"activity": {"name": "Threshold (demo)", "start_time_local": "2026-01-01T18:00:00",
                         "distance_meters": 10500, "moving_duration_seconds": 2900,
                         "avg_hr_bpm": LT1 - 3, "max_hr_bpm": LT2 + 3, "elevation_gain_meters": 40},
            "hr_zones": z, "planned": "2 km WU · 5 × 1 km @ threshold (90 s) · 2 km CD"}


def main():
    ap = argparse.ArgumentParser(description="Rich post-workout metrics for one run.")
    ap.add_argument("json", nargs="?", help="gathered workout JSON (MCP outputs)")
    ap.add_argument("--json", dest="json_opt", help="same as positional")
    ap.add_argument("--demo", nargs="?", const="threshold", choices=["threshold", "long"],
                    help="run on embedded demo data")
    ap.add_argument("--out", help="also write computed metrics to this JSON path")
    args = ap.parse_args()

    if args.demo:
        inp = demo_input(args.demo)
    else:
        path = args.json_opt or args.json
        if not path:
            ap.error("give a workout JSON path, or use --demo")
        with open(path) as f:
            inp = json.load(f)

    metrics = compute(inp)
    print(render(metrics))
    if args.out:
        with open(args.out, "w") as f:
            json.dump(metrics, f, indent=1, ensure_ascii=False)
        print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
