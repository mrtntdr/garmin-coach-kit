---
name: morning-plan
description: Morning training briefing. Use each morning to see today's planned session from the training plan cross-checked against Garmin overnight readiness (HRV, training readiness, sleep, body battery, RHR), get a go / adjust call, the right HR ceiling for today's run type, and the best weather window to run. Appends the briefing to the training log.
---

# Morning plan briefing

Produce a short, decision-oriented briefing for **today's** run: what's planned, whether the body is ready, what HR to hold, and when to go. Use `currentDate` from context as "today" (`YYYY-MM-DD`).

## Steps

1. **Read the athlete config.** `athlete.json` holds the anchors (`hr_max`, `hr_rest`, `lt1`, `lt2`, `threshold_pace`, `goal_marathon_pace`), the location, and the paths of the plan (`plan_file`) and log (`log_file`). Use these everywhere below — never assume numbers.

2. **Read the plan — via the extract.** Run `python3 scripts/plan_today.py`: it prints today's and tomorrow's rows from `plan_file` with their week heading and table header (session type, detail, target km). Check tomorrow so today doesn't trash the legs before a long run. Read `plan_file` itself only if the extract says there's no dated row (e.g. a plan written as a weekly template). No plan or no entry → say so and treat today as an easy day unless the user says otherwise.

3. **Read recent context.** The last ~40 lines of `log_file` (`tail -40`), so the briefing reflects how the week has actually gone. Don't read the whole log.

4. **Pull readiness + weather in ONE command:**
   ```
   python3 scripts/fetch_readiness.py
   ```
   Returns one compact JSON. HRV and forecast rows are packed strings; the `_legend` key decodes them. Contents: Garmin training readiness (often n/a — normal), 7-night HRV trend (`wk` weekly avg, **`n` nightly avg** vs the `[baseline]` band, `hi` 5-min high, status — judge the night by `n`, not `hi`; add `--hrv-days 14` for more), last night's sleep (hours/score/stages/overnight HRV/sleep stress), body battery, RHR (today + 7-day avg + `partial_sync` flag), **training load** (`load`: TRIMP and Garmin load over 7 vs 28 days, both acute:chronic ratios, and `last_hard` = the most recent hard day with its reason), morning weight (today + 7-day avg), and an hourly forecast 06–21 for the configured location: temp/feels, dew point, heat level, wind speed + the direction it blows FROM, rain, UV (`forecast` is null if no lat/lon is set). Auth is the cached Garmin token (`~/.garminconnect`) — no MFA.
   - **If the script fails with a token error**, tell the user to run `python3 scripts/login.py` once in a terminal. Don't try to log in yourself.
   - **Fallback if the script fails for any other reason:** Garmin MCP `get_training_readiness`, `get_hrv_data`, `get_sleep_data`, `get_body_battery`, `get_rhr_day`, `get_stats`, plus WebFetch on Open-Meteo for the forecast (lat/lon/timezone from `athlete.json`, hourly temperature, humidity, rain, wind, UV). Work out dew point yourself.
   - **Partially synced day:** `sleep.hours` 0 with null stages, no HRV row for today, body battery near zero, or `rhr.partial_sync` true (`day_min_hr` above `rhr.today`, which is impossible) all mean the watch hasn't finished syncing. Say so and suggest re-running after a sync. Don't make up a behavioural explanation.

5. **Interpret.** Judge readiness on the **HRV trend + recent load**, not on one night's noise. For load use `load`: an acute:chronic ratio of ~0.8–1.3 is a steady build, >1.5 a spike (after a layoff the chronic base is small, so the ratio overstates it). If the two ratios disagree, TRIMP-high means volume-driven, Garmin-high means intensity-driven. `last_hard.days_ago` = 0–1 before a planned quality session is the case to flag; it isn't a reason to skip an easy run. A night *above* the baseline band after a short night or a hard day is usually a rebound, not a warning, unless RHR is up too. Garmin's RHR is preliminary early in the morning; if `rhr.preliminary` is true, lean on the 7-day average.
   **Weight (optional):** if the user tracks weight, report `weight.today` and the 7-day average in one line, and judge only the average (single days swing 1–2 kg). If `today` is null and they track it, ask. When they answer, they can log it with the Garmin MCP `add_weigh_in` (it asks permission). Weight never changes the run call.

6. **Make the call:** **GO as planned** / **GO but adjust** (say how) / **EASY/REST**. Only call EASY/REST if readiness is genuinely down: HRV well below its baseline (status UNBALANCED/LOW, or >10 % below the weekly average), or poor sleep + low body battery + raised RHR together. **Easy running defaults to yes.** Save caution for intensity.

## HR bands (derive from athlete.json)

| Session | HR band | Note |
|---|---|---|
| **Recovery** (day after a hard session) | ≤ **LT1 − 8** | Staying low is the point |
| **Easy** | **LT1 − 10 … LT1** | Let it float, don't fight hills |
| **Long run** | start **LT1 − 10 … LT1 − 5**, allow late drift to **~LT1 + 4** | Late cardiac drift is normal. Don't *start* high |
| **Marathon pace** | `goal_marathon_pace`, HR well under LT2 | — |
| **Threshold** | ≤ **LT2** at `threshold_pace` | Main failure mode is running too fast. Prescribe by pace, cap by HR |

Always give today's **ceiling**, not just a number.

## Weather → timing & HR logic

- **Pick the window by session type.** Easy runs are flexible: any convenient hour. Quality sessions and the long run should go in the **coolest, least windy window**.
- **Judge heat by `heat` / `dew`, not temperature.** WBGT = 0.7×wet-bulb + 0.2×globe + 0.1×dry-bulb, so humidity outweighs sun ~3.5×, and plain air temperature is the smallest term. Dew point: **<12 negligible · 12–16 noticeable · 16–18 moderate · 18–21 significant · >21 severe.** Still air (<5 km/h) makes it worse.
- **Heat raises HR ~5–10 bpm** at the same effort. On warm days, judge easy runs by breathing and feel, and let HR sit at the top of the easy band.
- **Heat hurts threshold/MP pace more than easy pace.** If the only window is hot, hold the HR ceiling and accept a slower pace.
- Weather sets kit and timing. It is not a reason to skip an easy run. Mention rain, strong wind (>20 km/h, matters most for paced work) and high UV when relevant.
- **Wind direction:** on an out-and-back with noticeable wind (≳10 km/h), suggest heading out INTO the wind (it blows FROM the compass point given) and coming home with it, so the hard leg comes while fresh and the tailwind helps when HR would otherwise drift.

## Output (to chat)

- Header: `🏃 <date> — <day>: <planned session>`
- 2–4 bullets on readiness (HRV trend, sleep, body battery/RHR, and **load**: both acute:chronic ratios + the last hard day)
- **The call** in one bold line, with the specific adjustment if there is one
- **Today's HR ceiling** and pace targets, so it's usable on the road
- **Weight** (only if tracked): today + 7-day average in one line
- **Best window:** recommended time plus one line of conditions (temp/feels-like, dew, wind + direction, rain)

## Log

Append to `log_file` under a `## <date>` heading (create the file with a title if it's missing):

```
### <date> <day> — morning
- Planned: <session> (<km>) · HR ceiling <band>
- Readiness: <score/status> · HRV <val> vs <baseline> · sleep <h> · BB <n> · RHR <n>
- Load: ACWR <trimp> TRIMP / <garmin> Garmin · last hard <date> <what> (<n> d ago)
- Weather: best window <time> · <temp/feels>°C · dew <n> · wind <n> · rain <n>%
- Call: <go / adjust / easy> — <reason in a few words>
```

If there's already a morning entry for today, update it rather than adding a second one.
