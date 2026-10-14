"""Athlete config loader. Reads athlete.json from the kit root (or $ATHLETE_CONFIG)."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.environ.get("ATHLETE_CONFIG", os.path.join(ROOT, "athlete.json"))


def load():
    if not os.path.exists(PATH) and "--demo" in sys.argv:
        # demos run before setup: use the example anchors
        with open(os.path.join(ROOT, "athlete.example.json")) as f:
            return json.load(f)
    if not os.path.exists(PATH):
        sys.exit(f"No athlete config at {PATH}.\n"
                 f"Copy athlete.example.json to athlete.json and fill in your HR anchors.")
    with open(PATH) as f:
        return json.load(f)


CFG = load()
HR_MAX, HR_REST = CFG["hr_max"], CFG["hr_rest"]
LT1, LT2 = CFG["lt1"], CFG["lt2"]
LOCATION = CFG.get("location") or {}
