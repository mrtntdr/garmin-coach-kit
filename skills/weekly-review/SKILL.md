---
name: weekly-review
description: Weekly training review. Use at the end of a week (or any time you want a week summary) to pull the week's activities from Garmin, total the volume, compare against the training plan, check fitness trends (HRV, VO2max, race prediction), and write a dated review to the training log.
---

# Weekly review

Summarise the training week and grade it against the plan. Default to the Mon–Sun week containing `currentDate`. If the user names a week or date, use that.

## Steps

1. **Read `athlete.json`** for the anchors and the `plan_file` / `log_file` paths.

2. **Find the week in the plan — via the extract.** Run `python3 scripts/plan_today.py <any date in the week> --week`: every row of that Mon–Sun week with its heading (target volume). Read `plan_file` itself only if there's no dated row.

3. **Pull the week in ONE command:**
   ```
   python3 scripts/fetch_week.py              # this week
   python3 scripts/fetch_week.py 2026-07-05   # the week containing that date
   ```
   Returns every activity of the week as a compact line (km, pace, HR, TE, load, elevation), total volume, HRV weekly average at both ends of the week, VO2max, and Garmin's current race predictions. Token error → the user runs `python3 scripts/login.py` once. Fallback for any other failure: Garmin MCP `get_activities_by_date`, `get_hrv_data`, `get_vo2max_trend`, `get_race_predictions`.
   ("road"/"trail" reflects the activity type picked on the watch, not the real surface.)

4. **Read `log_file` from the week's Monday heading onward only** (`grep -n '^## <Monday date>'`, then read from that line) for the week's morning/workout entries. Reuse the splits, verdicts and 80/20 lines already there instead of working them out again.

5. **Grade the week:**
   - Volume vs target (and was a cutback week actually a cutback?)
   - Quality sessions done, and on target?
   - Long run distance and any MP segment
   - Easy days actually easy?
   - Readiness trend (HRV) across the week: building fitness or digging a hole?
   - Week-on-week volume change. Flag ramps above ~10 %/week, especially after a break.
   - Garmin's short-distance race predictions (5K/10K) are usually reliable. The marathon figure is an extrapolation, so don't steer by it.

## Output

Print to chat:
- Header: `📅 <range> — <volume> km (target <n>) · <grade>`
- Planned vs actual per session (table or bullets)
- 3–5 bullets: what went well, what slipped, what the trends say
- **Next week:** 1–2 adjustments if the data calls for them

## Log

Append to `log_file`:

```
## Week review — <range>
- Volume: <actual> / <target> km
- Sessions: <quality done & quality> · long run <km>
- Trends: HRV <dir> · VO2max <val> · race pred <time>
- Grade: <A–F or on-track/behind/ahead>
- Notes: <2–3 lines: wins, misses, what to change next week>
```

Write all dates as absolute dates.
