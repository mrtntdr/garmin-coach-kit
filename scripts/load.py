"""Training-load summaries for the fetch scripts: TRIMP and Garmin load, acute vs
chronic, and the last hard day.

Two load models, both reported because they disagree usefully:
  - TRIMP (Banister, from avg HR × duration, RUNS ONLY). Weights long steady runs.
  - Garmin load (Firstbeat EPOC, ALL activities incl. strength). Weights intensity
    ~2× what TRIMP does.
  TRIMP-hot + Garmin-normal = volume-driven; Garmin-hot = intensity-driven.

Acute:chronic ratio = last 7 days ÷ (last 28 days / 4). ~0.8–1.3 is the usual
"steady build" band; >1.5 is a spike. A ratio is only as good as its chronic base:
after a layoff the denominator is small and the ratio overstates the risk.
"""
import datetime
import math

from config import CFG, HR_MAX, HR_REST

RUN_TYPES = {"running", "trail_running", "track_running", "treadmill_running"}

# Banister weighting by sex: 0.64·e^(1.92x) (male) or 0.86·e^(1.67x) (female)
_K = {"female": (0.86, 1.67)}.get((CFG.get("sex") or "male").lower(), (0.64, 1.92))


def trimp(dur_s, avg_hr):
    """Banister TRIMP for a duration (s) at an average HR."""
    if not dur_s or not avg_hr:
        return 0.0
    hrr = max(0.0, min(1.0, (avg_hr - HR_REST) / (HR_MAX - HR_REST)))
    a, b = _K
    return (dur_s / 60) * hrr * a * math.exp(b * hrr)


def is_hard(a):
    """Why an activity counts as a hard day, or None. Hard = aerobic TE ≥4.0
    (threshold, tempo, races, hard orienteering), anaerobic TE ≥3.0 (real
    intervals), or ≥90 min (a long run costs a day too).

    Anaerobic TE alone is a poor signal below ~3: a few strides or hill sprints at
    the end of an easy run read 1.5–2.5 without making it a hard day."""
    if (a.get("aerobicTrainingEffect") or 0) >= 4.0:
        return f'aerobic TE {a["aerobicTrainingEffect"]:.1f}'
    if (a.get("anaerobicTrainingEffect") or 0) >= 3.0:
        return f'anaerobic TE {a["anaerobicTrainingEffect"]:.1f}'
    if (a.get("duration") or 0) >= 90 * 60:
        return f'{(a.get("duration") or 0) / 60:.0f} min'
    return None


def day_of(a):
    return datetime.date.fromisoformat((a.get("startTimeLocal") or "")[:10])


def ratio(acute, chronic_total):
    return round(acute / (chronic_total / 4), 2) if chronic_total else None


def summarize(acts, end):
    """Load summary for the 28 days ending on `end` (a date), from activity dicts
    as returned by get_activities_by_date. Pure function: easy to test."""
    a7 = end - datetime.timedelta(days=6)
    a28 = end - datetime.timedelta(days=27)
    t7 = t28 = g7 = g28 = 0.0
    last_hard = None
    for a in acts:
        d = day_of(a)
        if not a28 <= d <= end:
            continue
        run = (a.get("activityType") or {}).get("typeKey") in RUN_TYPES
        t = trimp(a.get("duration"), a.get("averageHR")) if run else 0.0
        gl = a.get("activityTrainingLoad") or 0.0
        t28 += t; g28 += gl
        if d >= a7:
            t7 += t; g7 += gl
        why = is_hard(a)
        if why and (last_hard is None or d >= last_hard[0]):
            last_hard = (d, why, a.get("activityName"))
    out = {"trimp_7d": round(t7), "trimp_28d": round(t28), "trimp_acwr": ratio(t7, t28),
           "garmin_load_7d": round(g7), "garmin_load_28d": round(g28),
           "garmin_acwr": ratio(g7, g28)}
    if last_hard:
        out["last_hard"] = {"date": last_hard[0].isoformat(),
                            "days_ago": (end - last_hard[0]).days,
                            "why": last_hard[1], "name": last_hard[2]}
    else:
        out["last_hard"] = None
    return out


def week_trimp(acts, mon):
    """TRIMP for the Mon–Sun week starting `mon`, and its ratio to the mean of the
    4 weeks before it (calendar weeks)."""
    def total(start):
        end = start + datetime.timedelta(days=6)
        return sum(trimp(a.get("duration"), a.get("averageHR")) for a in acts
                   if (a.get("activityType") or {}).get("typeKey") in RUN_TYPES
                   and start <= day_of(a) <= end)
    this = total(mon)
    prior = [total(mon - datetime.timedelta(weeks=k)) for k in range(1, 5)]
    mean = sum(prior) / 4
    return {"week_trimp": round(this), "prior_4wk_mean_trimp": round(mean),
            "week_vs_prior_4wk": round(this / mean, 2) if mean else None}


def fetch(g, end, days_back=34):
    """Activities from `days_back` days before `end` through `end`."""
    start = end - datetime.timedelta(days=days_back)
    return g.get_activities_by_date(start.isoformat(), end.isoformat()) or []
