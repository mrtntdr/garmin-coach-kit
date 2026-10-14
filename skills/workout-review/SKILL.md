---
name: workout-review
description: Post-workout review. Use right after a run to pull the just-completed activity from Garmin, compare it against the planned session in the training plan (pace, HR, splits, intervals), and judge execution with true time-in-zone 80/20, TRIMP, efficiency factor and aerobic decoupling. Appends the review to the training log.
---

# Post-workout review

Review the run the athlete **just finished today** against the plan. Use `currentDate` as "today".

## Steps

1. **Read `athlete.json`** for the anchors (`lt1`, `lt2`, `hr_max`, `threshold_pace`, `goal_marathon_pace`) and the `plan_file` / `log_file` paths.

2. **Pull everything in ONE command:**
   ```
   python3 scripts/fetch_workout.py --review              # today
   python3 scripts/fetch_workout.py 2026-07-05 --review   # specific date
   ```
   This prints (a) one JSON with every activity of the day: summary, per-lap splits (pace/HR/power/cadence/elevation), true HR time-in-zones, and weather already converted °F→°C with dew point; and (b) a metrics digest for the newest run: **TRUE time-in-zone 80/20**, TRIMP, EF, aerobic decoupling, first-half vs second-half drift.
   - If there are several runs, review the most recent one unless the user named another. The JSON has them all.
   - **Token error** → tell the user to run `python3 scripts/login.py` once in a terminal.
   - **Fallback if the script fails for any other reason:** Garmin MCP `get_activities_fordate` → `get_activity` + `get_activity_splits` + `get_activity_hr_in_timezones` + `get_activity_weather`. ⚠️ The weather tool returns **°F in a field named `temperature_celsius`**, with no dew point. Save the results as `{activity, splits, hr_zones, weather, planned}` and run `python3 scripts/workout_review.py <file>`. It converts the °F.
   - To re-run the metrics on another run, write its `{activity, splits, hr_zones, weather, planned}` entry to a file and run `python3 scripts/workout_review.py <file>`.

3. **Read the plan — via the extract.** Run `python3 scripts/plan_today.py [date]` and take today's row (read `plan_file` itself only if there's no dated row). For context on the week so far, `tail -40` the `log_file`; don't read the whole log. Pull out the prescribed structure (e.g. `2 × 10 min @ threshold, 2 min jog`, `last 6 km @ MP`, `easy ≤ LT1`).

4. **Compare execution** against the anchors:
   - **Threshold / MP reps:** did the working splits hit target pace? Was HR in range, or drifting up? Were the recoveries respected? On **short reps (≤ ~1.5 km) judge by PACE.** HR lags, so a rep-average HR well under LT2 is normal, not under-effort.
   - **Easy / long:** did HR stay under the cap, or creep up (heat, fatigue, starting too fast)? Look for cardiac drift across the run.
   - **Decoupling is meaningless on interval sessions.** Only quote it for steady runs of ~50 min or more. Rough guide: <5 % excellent · 5–10 % moderate · >10 % poor. It is also confounded by one-sided wind (tailwind out, headwind home) and net-uphill second halves. Ask or check the elevation before reading it as fitness.
   - **Report the true time-in-zone 80/20 from the script**, not the avg-HR label. A threshold session read by average HR looks "easy"; that's exactly what the script corrects.
   - Distance vs target km. Check heat (dew point) before blaming fitness for a high HR.

## Output

Print to chat:
- Header: `✅ <date> — <session>: <one-line verdict>` (nailed it / solid / under-cooked / over-cooked / aborted)
- Actual vs planned: distance, avg pace/HR, and the key working splits
- 2–3 bullets on what stood out (pace control, HR drift, true 80/20, signs of fatigue)
- One forward-looking note if it's useful

## Log

Append to `log_file` under today's `## <date>` heading (below any morning entry):

```
### <date> <day> — workout
- Planned: <session>
- Actual: <dist> km · <avg pace> · HR <avg>/<max> · TE <aerobic>/<anaerobic> · TRIMP <n>
- Splits: <key working splits>
- 80/20 (true time-in-zone): easy <e>% · mod <m>% · hard <h>% · decoupling <d>%
- Verdict: <nailed / solid / under / over> — <one line>
```

Keep the working-split line so the weekly review can spot trends without asking Garmin again.
