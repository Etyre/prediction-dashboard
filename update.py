#!/opt/homebrew/bin/python3
"""Hourly job: rebuild docs/data.json and push it if it changed.

Run by the launchd agent com.elityre.prediction-dashboard. Pushing to main is
what updates the public page (GitHub Pages serves docs/). Only docs/data.json
is ever committed here, so half-finished edits elsewhere are never published.
Log: ~/Library/Logs/prediction-dashboard.log.
"""
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent


def log(msg):
    for line in str(msg).strip().splitlines():
        print(f"{datetime.now():%Y-%m-%d %H:%M:%S} {line}", flush=True)


def run(*cmd, quiet=False):
    r = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True)
    out = (r.stdout + r.stderr).strip()
    # quiet: the output is an answer for this script, not news for the log.
    if out and not (quiet and r.returncode == 0):
        log(out)
    if r.returncode:
        log(f"FAILED ({r.returncode}): {' '.join(cmd)}")
        sys.exit(1)
    return r.stdout


def main():
    run(sys.executable, "build.py")
    if run("git", "status", "--porcelain", "docs/data.json", quiet=True).strip():
        run("git", "add", "docs/data.json")
        run("git", "commit", "-q", "-m", "Update predictions from Fatebook", "--", "docs/data.json")
    # Also covers a commit whose push failed on an earlier run.
    if run("git", "rev-list", "--count", "@{u}..HEAD", quiet=True).strip() != "0":
        run("git", "push", "-q")
        log("pushed")


if __name__ == "__main__":
    main()
