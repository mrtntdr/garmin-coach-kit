#!/usr/bin/env python3
"""login.py — one-time interactive Garmin login that caches a session token.

Run this once in a terminal (it may ask for an MFA code). Afterwards every fetch_*
script resumes the cached token silently, so they are safe to run from Claude Code.

Credentials: $GARMIN_EMAIL / $GARMIN_PASSWORD if set, otherwise prompted.
Token dir: ~/.garminconnect (override with $GARMINTOKENS). Re-run when it expires.
"""
import getpass
import os

from garminconnect import Garmin

TOKENSTORE = os.environ.get("GARMINTOKENS", os.path.expanduser("~/.garminconnect"))


def main():
    email = os.environ.get("GARMIN_EMAIL") or input("Garmin email: ")
    pw = os.environ.get("GARMIN_PASSWORD") or getpass.getpass("Garmin password: ")
    g = Garmin(email, pw, prompt_mfa=lambda: input("MFA code: "))
    g.login()
    os.makedirs(TOKENSTORE, exist_ok=True)
    g.garth.dump(TOKENSTORE)
    print(f"Token cached to {TOKENSTORE}. Logged in as {g.get_full_name()}.")


if __name__ == "__main__":
    main()
