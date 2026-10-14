#!/usr/bin/env python3
"""plan_today.py [YYYY-MM-DD] [--week]

Prints only the part of the plan a skill needs, instead of the whole file:
the heading of the week that contains the date, the table header, and the rows
for that date and the next day (--week: every row of that week).

Works with any markdown plan that has one row (or line) per day containing an
ISO date (YYYY-MM-DD), like examples/plan.example.md. The plan path comes from
`plan_file` in athlete.json. If no row matches, says so, so the skill can fall
back to reading the plan itself.
Output: plain markdown on stdout.
"""
import datetime
import os
import re
import sys

from config import CFG, ROOT

DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


def extract(lines, day, week=False):
    want = {day.isoformat(), (day + datetime.timedelta(days=1)).isoformat()}
    if week:
        mon = day - datetime.timedelta(days=day.weekday())
        want = {(mon + datetime.timedelta(days=i)).isoformat() for i in range(7)}
    out, heading, header, shown = [], None, None, set()
    for i, line in enumerate(lines):
        if line.startswith("#"):
            heading, header = line, None
            continue
        # a table header is the row directly above a |---| separator
        if line.startswith("|") and i + 1 < len(lines) and lines[i + 1].startswith("|--"):
            header = (i, [line, lines[i + 1]])
            continue
        # a row is a session row when its FIRST date is one we want
        first = DATE.search(line)
        if first and first.group(1) in want:
            if heading and heading not in shown:
                out += ["", heading]
                shown.add(heading)
            if header and header[0] not in shown:     # keyed by line number
                out += header[1]
                shown.add(header[0])
            out.append(line)
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    day = datetime.date.fromisoformat(args[0]) if args else datetime.date.today()
    path = os.path.join(ROOT, CFG.get("plan_file") or "plan.md")
    if not os.path.exists(path):
        sys.exit(f"No plan at {path} (set plan_file in athlete.json).")
    lines = open(path, encoding="utf-8").read().splitlines()
    rows = extract(lines, day, week="--week" in sys.argv)
    print(f"# {os.path.basename(path)} extract for {day} ({day:%a})")
    print("\n".join(rows).strip() if rows else
          "(no dated row for this date — read the plan file itself, or treat today as easy)")


if __name__ == "__main__":
    main()
