#!/opt/homebrew/bin/python3
"""Builds docs/data.json, the only data the public prediction dashboard shows.

Downloads every question the Fatebook API key can see, keeps only the ones
shared publicly that I forecasted on, and writes just the title, dates,
resolution, my own tags on it and my own forecasts. Everything else (private
questions and their tags, comments, other people's forecasts) is dropped here and never reaches docs/.
The one thing derived from private questions is the "all predictions"
calibration: ten bucket counts, with no titles or individual forecasts.

Config: config.env beside this file (FATEBOOK_API_KEY, FATEBOOK_USER_ID,
INCLUDE_UNLISTED). Log: ~/Library/Logs/prediction-dashboard.log (written by
update.sh, which runs this under launchd). Standard library only.

  build.py          fetch from Fatebook and rewrite docs/data.json if changed
  build.py --test   run the filter on test/fixture.json and check nothing private leaks
"""
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "docs" / "data.json"
API = "https://fatebook.io/api/v0/getQuestions"
PAGE = 100


def read_config():
    cfg = {}
    for line in (HERE / "config.env").read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            cfg[k.strip()] = v.strip()
    return cfg


def fetch_all(api_key):
    items, cursor = [], 0
    while True:
        qs = urllib.parse.urlencode({"apiKey": api_key, "limit": PAGE, "cursor": cursor})
        with urllib.request.urlopen(f"{API}?{qs}", timeout=60) as r:
            got = json.load(r)["items"]
        items += got
        if len(got) < PAGE:
            return items
        cursor += PAGE


def question_url(q):
    # Fatebook reads the id after "--"; the slug before it is only for humans.
    slug = re.sub(r"[^a-z0-9]+", "-", q["title"].lower())[:60].strip("-")
    return f"https://fatebook.io/q/{slug}--{q['id']}"


def public_view(questions, user_id, include_unlisted, now):
    """The filter. Anything not returned here is never published."""
    out = []
    for q in questions:
        if q.get("sharedPublicly") is not True:
            continue
        # "Unlisted" means link-only on Fatebook: off unless explicitly opted in.
        if q.get("unlisted") is not False and not include_unlisted:
            continue
        # Forecasts I chose to hide on Fatebook stay hidden here too.
        hide_until = q.get("hideForecastsUntil")
        if q.get("hideForecastsUntilPrediction") or (hide_until and hide_until > now):
            continue
        mine = my_forecasts(q, user_id)
        if not mine:
            continue
        out.append({
            "id": q["id"],
            "title": " ".join(q["title"].split()),
            "url": question_url(q),
            "createdAt": q["createdAt"],
            "resolveBy": q["resolveBy"],
            "resolvedAt": q.get("resolvedAt"),
            "resolution": q.get("resolution") if q.get("resolved") else None,
            "type": q.get("type"),
            # My own tags only; they are published because the page filters by them.
            "tags": sorted({t["name"] for t in q.get("tags", []) if t.get("userId") == user_id}),
            "forecasts": mine,
        })
    out.sort(key=lambda q: q["createdAt"], reverse=True)
    return out


def my_forecasts(q, user_id):
    return sorted(
        ({"p": float(f["forecast"]), "t": f["createdAt"]} for f in q.get("forecasts", [])
         if f.get("userId") == user_id and f.get("forecast") is not None),
        key=lambda f: f["t"],
    )


def calibration(resolved):
    """Ten equal-width buckets from (resolution, forecasts) pairs.

    Same method as Fatebook's own chart: every forecast on a yes/no-resolved
    binary question counts once (not only the latest), except one I replaced
    within a minute. Only counts leave this function, never titles, which is
    what makes it safe to run over private questions for the "all" view.
    """
    bins = [{"lo": i * 10, "hi": (i + 1) * 10, "n": 0, "yes": 0, "sum": 0.0} for i in range(10)]
    for resolution, forecasts in resolved:
        if resolution not in ("YES", "NO"):
            continue
        times = [datetime.fromisoformat(f["t"].replace("Z", "+00:00")) for f in forecasts]
        for f, t in zip(forecasts, times):
            if any(0 < (u - t).total_seconds() < 60 for u in times):
                continue
            b = bins[min(int(f["p"] * 10), 9)]
            b["n"] += 1
            b["yes"] += resolution == "YES"
            b["sum"] += f["p"]
    return [{"lo": b["lo"], "hi": b["hi"], "n": b["n"], "yes": b["yes"],
             "mean": round(b["sum"] / b["n"], 4) if b["n"] else None} for b in bins]


def run_test():
    fixture = json.loads((HERE / "test" / "fixture.json").read_text())
    now = "2026-11-10T00:00:00.000Z"
    listed = public_view(fixture, "me", False, now)
    both = public_view(fixture, "me", True, now)
    text = json.dumps(both)
    assert [q["id"] for q in listed] == ["pub-open", "pub-yes"], [q["id"] for q in listed]
    assert {q["id"] for q in both} == {"pub-open", "pub-yes", "unlisted-no"}, [q["id"] for q in both]
    for leak in ("PRIVATE", "SECRET-TAG", "someone-else", "0.99", "HIDDEN", "NOT-MINE"):
        assert leak not in text, f"leaked: {leak}"
    assert listed[1]["tags"] == ["public-tag"] and listed[0]["tags"] == [], [q["tags"] for q in listed]
    assert [f["p"] for f in listed[1]["forecasts"]] == [0.6, 0.8], listed[1]["forecasts"]
    assert set(listed[0]) == {"id", "title", "url", "createdAt", "resolveBy", "resolvedAt", "resolution", "type", "tags", "forecasts"}
    cal = calibration([("YES", [{"p": 0.6, "t": "2026-01-01T00:00:00.000Z"}, {"p": 0.65, "t": "2026-01-01T00:00:30.000Z"}, {"p": 1.0, "t": "2026-01-02T00:00:00.000Z"}]),
                       ("NO", [{"p": 0.62, "t": "2026-01-01T00:00:00.000Z"}]), ("AMBIGUOUS", [{"p": 0.1, "t": "2026-01-01T00:00:00.000Z"}])])
    assert [(b["n"], b["yes"]) for b in cal] == [(0, 0)] * 6 + [(2, 1)] + [(0, 0)] * 2 + [(1, 1)], cal
    assert cal[6]["mean"] == 0.635 and set(cal[0]) == {"lo", "hi", "n", "yes", "mean"}
    print("test ok: private, hidden, unlisted, tag and other-user data all excluded")


def main():
    if "--test" in sys.argv:
        return run_test()
    cfg = read_config()
    key, user_id = cfg.get("FATEBOOK_API_KEY"), cfg.get("FATEBOOK_USER_ID")
    if not key or not user_id:
        sys.exit("config.env needs FATEBOOK_API_KEY and FATEBOOK_USER_ID")
    include_unlisted = cfg.get("INCLUDE_UNLISTED", "no").lower() in ("yes", "true", "1")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    everything = fetch_all(key)
    questions = public_view(everything, user_id, include_unlisted, now)
    # An empty result is far more likely a bad key or API change than a real
    # wipe-out, so refuse to publish a blank page over a working one.
    if not questions:
        sys.exit(f"no public predictions found among {len(everything)} questions; leaving {OUT.name} untouched")

    # "all" covers every binary question I forecast on, private ones included,
    # but only as bucket counts: the page's calibration toggle needs nothing more.
    cal = {
        "public": calibration((q["resolution"], q["forecasts"]) for q in questions if q["type"] == "BINARY"),
        "all": calibration((q.get("resolution"), my_forecasts(q, user_id)) for q in everything
                           if q.get("type") == "BINARY" and q.get("resolved")),
    }
    old = json.loads(OUT.read_text()) if OUT.exists() else {}
    if old.get("questions") == questions and old.get("calibration") == cal:
        print(f"no change ({len(questions)} public predictions)")
        return
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({"updated": now, "calibration": cal, "questions": questions}, indent=1) + "\n")
    print(f"wrote {len(questions)} public predictions (of {len(everything)} visible to the key)")


if __name__ == "__main__":
    main()
