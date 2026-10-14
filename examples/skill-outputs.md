# What the skills print — examples

Synthetic data, matching `plan.example.md` and `athlete.example.json`. The skills write the
compact version of each into the log (see `log.example.md`).

## `/morning-plan`

> 🏃 2026-10-07 — Wed: Threshold 3 × 8 min @ 4:30
>
> - HRV 58 last night, inside its 55–63 baseline; BALANCED all week
> - Sleep 7.1 h (score 81), body battery 78
> - RHR 51, same as the 7-day average
> - **Load: steady build, not a spike.** Acute:chronic 1.08 by TRIMP and 1.12 by Garmin load
>   (both inside 0.8–1.3). Last hard day was Sunday's 100-min long run, 3 days ago, with gym and
>   an easy run since, so the legs are fresh for reps
>
> **GO as planned.**
>
> **HR:** warm-up and jogs ≤150. Reps at **4:30/km, capped at 170**. If rep 3 is above 170 before
> half-way, finish it at 4:35 instead of forcing the pace.
>
> **⚖️ Weight:** 74.6 kg · 7-day avg 74.9 (6 days), flat
>
> **Best window: 18:00–19:00.** 11 °C (feels like 9), dew point 6 (no heat effect), wind 9 km/h
> from the SW, 10 % chance of rain. On an out-and-back, start into the wind (head SW) so the
> tailwind brings you home. Later is fine too; it only gets cooler.

<details><summary>The <code>load</code> block it was read from (<code>fetch_readiness.py</code>)</summary>

```json
"load": {"trimp_7d": 412, "trimp_28d": 1526, "trimp_acwr": 1.08,
         "garmin_load_7d": 655, "garmin_load_28d": 2340, "garmin_acwr": 1.12,
         "last_hard": {"date": "2026-10-04", "days_ago": 3, "why": "100 min",
                       "name": "Long Run"}}
```
</details>

## `/workout-review`

> ✅ 2026-10-07 — Threshold 3 × 8 min: nailed it
>
> | | planned | actual |
> |---|---|---|
> | distance | 9 km | 9.4 km |
> | reps | 3 × 8 min @ 4:30, HR ≤170 | 4:29 · 4:31 · 4:27 — HR 163 / 166 / 169 |
> | recoveries | 2 min jog | 2:00 · 2:05 |
>
> - **Pace control was good.** The reps were within 4 s of each other and the fastest came last,
>   when you had the most in hand.
> - **HR rose 3 bpm per rep.** That's normal drift and stayed under the ceiling. Next time, add
>   time (3 × 10 min) before adding pace.
> - **True time-in-zone: 55 % easy · 38 % moderate · 7 % hard.** Going by average HR (152), this
>   would count as an easy run.
> - Decoupling isn't meaningful for intervals, so it's skipped.
>
> Tomorrow is recovery: keep it ≤142 even if the legs feel fine.

## `/weekly-review`

> 📅 2026-10-05 .. 2026-10-11 — 41.2 km (target 40) · on track
>
> | day | planned | actual |
> |---|---|---|
> | Tue | easy 8 | 8.1 km, HR 144 ✅ |
> | Wed | threshold 3 × 8' | 9.4 km, reps 4:29/4:31/4:27 ✅ |
> | Thu | recovery 6 | 6.0 km, HR 139 ✅ |
> | Sat | easy + strides 6 | 6.4 km ✅ |
> | Sun | long 16 | 16.3 km, decoupling 3.1 % ✅ |
>
> - Every session done; easy days really were easy (average HR 139–146).
> - The long run held together: 3.1 % decoupling, and HR 141 → 153 across the run.
> - HRV was flat (57 → 58), so the load is being absorbed.
> - Volume was +7 % on last week, inside the 10 % guideline.
> - 10K prediction 45:20, down 20 s. That number is reliable; the marathon prediction isn't.
>
> **Next week:** keep the plan. Add the 4 km MP finish on Sunday, and on Wednesday add time to
> the reps (3 × 10 min) rather than speed.
