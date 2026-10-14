# Changelog

## 2.0 — 14 Oct 2026

### Fixed
- **Drift pace was wrong on runs with partial laps.** It averaged lap *durations*, which is
  only pace/km when every lap is exactly 1 km; an auto-lap remainder or a manual strides
  lap made a half read minutes too fast. Pace is now time ÷ distance per half, HR is
  time-weighted, and halves are split by distance.
- **Decoupling over-weighted short laps.** A 0.38 km final lap counted as a full lap in
  the half averages. EF per half is now total distance / total time over time-weighted HR.
- **Overnight HRV was always null.** `avgOvernightHrv` sits at the top of the sleep
  payload, not inside `dailySleepDTO`.
- **The forecast ignored the date argument.** `fetch_readiness.py 2026-10-15` returned
  today's weather; it now fetches the requested day.
- **HRV trend lacked the nightly average and baseline band**, so a night couldn't be
  judged against its baseline. Both are now in every row.
- **"Would call this 100% easy — this is the correction"** printed even when the true
  split was 98% easy. It now prints only when the coarse label is off by ≥10 points.
- `workout_review.py` crashed on an activity with no distance, pace or start time;
  `--demo` failed before `athlete.json` existed.
- Race predictions for 5K/10K/half came back as raw seconds; all are now h:mm:ss.
- RHR parsing no longer crashes when Garmin returns no metrics map; `partial_sync` flags
  the impossible min-HR-above-RHR case directly.

### Added
- `plan_today.py` — today's/tomorrow's (or the week's) plan rows instead of the whole file.
- Wind direction in the forecast, and a skill rule to head out into the wind.
- Morning weight (today + 7-day average) in `fetch_readiness.py`, optional in the skill.
- `tests/test_kit.py` — 15 golden-value tests, no login needed.
- Compact JSON output (packed HRV and forecast rows with a `_legend`), ~6× smaller.
