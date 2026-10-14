#!/usr/bin/env bash
# Sets up the kit: Python dependency, athlete config, skills, Garmin login.
set -euo pipefail
cd "$(dirname "$0")"

echo "1/4  Installing garminconnect"
python3 -m pip install --user -q -r requirements.txt

echo "2/4  Athlete config"
if [ ! -f athlete.json ]; then
  cp athlete.example.json athlete.json
  echo "     created athlete.json from the example. Edit your HR anchors and location."
else
  echo "     athlete.json already exists, left as is"
fi
[ -f plan.md ] || { cp examples/plan.example.md plan.md; echo "     created plan.md from the example"; }

echo "3/4  Installing skills into .claude/skills/"
mkdir -p .claude/skills
for d in skills/*/; do
  name=$(basename "$d")
  rm -rf ".claude/skills/$name"
  cp -R "$d" ".claude/skills/$name"
  echo "     /$name"
done

echo "4/4  Garmin login"
if [ -d "${GARMINTOKENS:-$HOME/.garminconnect}" ]; then
  echo "     token found, skipping (run python3 scripts/login.py to redo it)"
else
  python3 scripts/login.py
fi

command -v uvx >/dev/null || echo "Note: uv is not installed, so the Garmin MCP fallback won't start (brew install uv)."
echo "Done. Open Claude Code in this folder and run /morning-plan."
