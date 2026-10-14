# Garmin coach kit for Claude Code

Three Claude Code skills (morning briefing, post-workout review, weekly review) backed by
small Python scripts that pull everything from Garmin Connect in one command each. The
[Garmin MCP server](https://github.com/Taxuspt/garmin_mcp) is set up too, as a fallback
and for ad-hoc questions ("what was my longest run in May?").

## Setup

```bash
./install.sh
```

This installs `garminconnect`, creates `athlete.json` and `plan.md` from the examples,
copies the skills from `skills/` into `.claude/skills/` (where Claude Code looks for them),
and runs the Garmin login once (it may ask for an MFA code). Then edit `athlete.json` (HR
anchors, location) and replace `plan.md` with your own plan.

**Editing the skills:** change the files in `skills/`, then re-run `./install.sh`. It
overwrites `.claude/skills/` and leaves your config, plan and token alone.

Doing it by hand instead: `pip install -r requirements.txt`, `cp athlete.example.json athlete.json`,
`mkdir -p .claude/skills && cp -R skills/* .claude/skills/`, `python3 scripts/login.py`.

For the MCP server you also need [uv](https://docs.astral.sh/uv/) (`brew install uv`).
`.mcp.json` starts it with `uvx`, so there's nothing else to install.

`login.py` caches a session token in `~/.garminconnect` (override with `$GARMINTOKENS`).
After that, every script resumes the token silently, so Claude can run them without
prompting. When the token eventually expires the scripts say so. Just run `login.py` again.

**The scripts and the MCP server share the same token** (`~/.garminconnect`), so one login
covers both. The MCP server's own login works too:
`uvx --python 3.12 --from git+https://github.com/Taxuspt/garmin_mcp garmin-mcp-auth`
(add `--verify` to check it, or `--force-reauth` when it expires, roughly every 6 months).

Open Claude Code **in this folder** and use
`/morning-plan`, `/workout-review` or `/weekly-review`. The skills read a plan from
`plan_file` (any markdown with dated sessions) and append to `log_file`.

The first time, Claude Code asks you to approve the project MCP server (`garmin`) from
`.mcp.json`. Check it with `/mcp`. `.claude/settings.json` pre-approves the scripts and
the **read-only** Garmin tools the skills fall back to. Write tools (uploading workouts,
logging weight, changing activities) still ask for permission every time.

**Why scripts first, MCP as fallback?** One script call returns a compact JSON with the
unit fixes already applied. Pulling the same through MCP takes 5–10 tool calls and a lot
more context, and the MCP weather tool passes Garmin's °F-labelled-as-Celsius value
through unchanged.

## athlete.json

| key | meaning |
|---|---|
| `hr_max`, `hr_rest` | TRIMP anchors |
| `sex` | `male` or `female`: picks the Banister TRIMP weighting (0.64·e^1.92x / 0.86·e^1.67x). Default male |
| `lt1`, `lt2` | aerobic / lactate threshold HR. These drive the easy/moderate/hard 80/20 split |
| `threshold_pace`, `goal_marathon_pace` | min:sec per km |
| `location` | `lat`/`lon`/`timezone` for the Open-Meteo hourly forecast (`null` = skip) |
| `plan_file`, `log_file` | paths relative to this folder |

## Skills

| skill | file | when |
|---|---|---|
| `/morning-plan` | `skills/morning-plan/SKILL.md` | each morning: readiness → go/adjust call, HR ceiling, best weather window |
| `/workout-review` | `skills/workout-review/SKILL.md` | after a run: execution vs plan, true 80/20, TRIMP, EF, decoupling |
| `/weekly-review` | `skills/weekly-review/SKILL.md` | end of week: volume vs target, sessions, HRV/VO2max trend |

The skills run the scripts below with paths relative to this folder, so they are
installed per project (in `.claude/skills/`), not globally in `~/.claude/skills/`.

## Scripts

| script | used by | what it does |
|---|---|---|
| `login.py` | you, once | interactive login → cached token |
| `fetch_readiness.py [date] [--hrv-days N]` | morning-plan | readiness, 7-night HRV (vs baseline band), sleep, body battery, RHR, weight, hourly forecast with dew point, heat-stress level and wind direction for that date |
| `plan_today.py [date] [--week]` | all three | today's + tomorrow's rows of `plan_file` (or the whole week), with heading and table header |
| `fetch_workout.py [date] [--review]` | workout-review | the day's activities, laps, HR time-in-zone, weather (°C); `--review` adds the metrics digest |
| `workout_review.py <file> \| --demo [long]` | workout-review | true time-in-zone 80/20, TRIMP, EF, decoupling, drift |
| `fetch_week.py [date]` | weekly-review | Mon–Sun activities, totals, HRV endpoints, VO2max, race predictions (5K/10K/half/marathon as h:mm:ss) |
| `load.py` | readiness, week, workout | TRIMP (runs) and Garmin load (all activities): 7d vs 28d acute:chronic, week vs prior 4 weeks, last hard day |
| `garmin_client.py`, `config.py` | all | token auth, unit fixes, config loading |

| config file | what it does |
|---|---|
| `.mcp.json` | registers the Garmin MCP server for this folder |
| `install.sh` | one-step setup (see above) |
| `.claude/settings.json` | enables it and pre-approves the scripts and read-only Garmin tools |

## Examples

`examples/` shows what the skills need and what they produce (all synthetic):

| file | what it is |
|---|---|
| `plan.example.md` | a two-week plan in a format the skills can read. Copy it to `plan.md` to start |
| `log.example.md` | what the skills append to `log.md`: morning, workout and week-review entries |
| `skill-outputs.md` | what each skill prints in chat |

Try `python3 scripts/workout_review.py --demo` (or `--demo long`) to see the metrics without touching Garmin. It works before setup too.

## Tests

```bash
python3 tests/test_kit.py
```

No login or network needed. The metrics fail silently (a wrong decoupling is still a
plausible number), so run this after touching any formula.

## Keeping the token cost low

The skills are written to read as little as possible:

- **Plan:** `plan_today.py` hands over today's and tomorrow's rows, not the whole plan.
- **Readiness:** HRV and forecast rows are packed into one short string each, with a
  `_legend` key that decodes them. A morning pull is ~1.5 KB.
- **Log:** the skills `tail` the log or read from the week's Monday heading, never the
  whole file. Once a month, move the previous month's complete weeks into
  `log-YYYY-MM.md` so `log.md` stays short.
- Keep any `CLAUDE.md` you add to this folder short. It loads in full every session.

## Gotchas this handles

- Garmin's activity weather reports **°F in a field named `temperature_celsius`**, and gives
  no dew point. The scripts convert and compute it.
- Classifying a run by its **average HR** puts a threshold session in the "easy" bucket.
  `workout_review.py` uses the real seconds-in-zone and splits Garmin zones across your LT1/LT2.
- Early-morning RHR is **preliminary**, and a partly synced day can show impossible values
  (min HR above RHR, 0 h sleep). The morning skill spots these and tells you to re-sync.

## Licence

MIT, see `LICENSE`. Not affiliated with Garmin. Uses the unofficial
[garminconnect](https://github.com/cyberjunky/python-garminconnect) library and the
[Garmin MCP server](https://github.com/Taxuspt/garmin_mcp).
