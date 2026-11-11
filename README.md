# prediction-dashboard

A public web page showing my Fatebook calibration chart and a keyword-searchable list of the predictions I have shared publicly on Fatebook. Built 2026-11-10 so anyone can see my track record without a Fatebook account. Live at https://etyre.github.io/prediction-dashboard/.

## How it works

- `build.py` downloads every question my Fatebook API key can see (`/api/v0/getQuestions`, 100 per page) and writes `docs/data.json`.
- Only questions that are shared publicly **and** listed on fatebook.io/public, that I forecasted on, and whose forecasts are not hidden, go into the list. For each one it keeps the title, dates, resolution and my own forecasts. Tags, comments, notes and other people's forecasts are dropped.
- The calibration chart has a toggle: **Public predictions** (the listed ones above) or **All predictions** (every binary question I forecasted on that resolved yes or no, private ones included). For "all", only ten bucket counts are published: no titles, no individual forecasts.
- Calibration uses Fatebook's own method: every forecast counts once (not just the latest), except one replaced within a minute; ten equal-width buckets; ambiguous resolutions are left out.
- `docs/index.html` is a static page with no dependencies. It fetches `data.json`, draws the chart as SVG, and filters the list as you type: every word typed must appear in the title.
- GitHub Pages serves the `docs/` folder of the `main` branch of the public repo `Etyre/prediction-dashboard`.
- A launchd agent runs `update.py` at login and every hour. It runs `build.py`, and if `docs/data.json` changed, commits just that file and pushes. The page updates a minute or so after the push.

## Files

| File | Purpose |
|---|---|
| `build.py` | Fetches from Fatebook, filters to what is public, writes `docs/data.json`. `--test` runs the filter on the fixture. |
| `update.py` | The hourly job: build, then commit and push `docs/data.json` if it changed. |
| `docs/index.html` | The whole public page: chart, toggle, search, list. |
| `docs/data.json` | Generated. The only data the page shows. |
| `test/fixture.json` | Fake questions (public, link-only, private, hidden, someone else's) for `--test`. |
| `com.elityre.prediction-dashboard.plist` | launchd agent definition. |
| `install.sh` | Copies the plist into place and restarts the agent. |
| `config.env.example` | Template for `config.env`. |

## Runtime locations

- Config and secret: `config.env` in this folder (untracked).
- Raw API dump from development: `raw/` (untracked; contains private questions, never commit).
- Log: `~/Library/Logs/prediction-dashboard.log`.
- Installed agent: `~/Library/LaunchAgents/com.elityre.prediction-dashboard.plist`. It runs the code in this folder directly; there is no separate installed copy.
- No state file: `docs/data.json` in git is the state.

## Common tasks

```sh
./build.py --test                 # prove the privacy filter and calibration maths, no network
./build.py                        # refresh docs/data.json from Fatebook
python3 -m http.server 8791 --directory docs   # preview at http://localhost:8791 (file:// will not load data.json)
./update.py                       # build, commit and push now
./install.sh                      # install or restart the hourly agent
launchctl kickstart gui/$(id -u)/com.elityre.prediction-dashboard   # run the agent now
launchctl bootout gui/$(id -u)/com.elityre.prediction-dashboard     # stop it
tail -f ~/Library/Logs/prediction-dashboard.log
```

## Settings that matter

- `config.env`: `FATEBOOK_API_KEY` (from https://fatebook.io/api-setup), `FATEBOOK_USER_ID`, and `INCLUDE_UNLISTED`.
- `INCLUDE_UNLISTED=yes` also publishes questions that are shared by link only and not shown on fatebook.io/public. Off by default because that would make link-only questions discoverable.
- To publish or unpublish a prediction, change its sharing on Fatebook; the page follows within the hour.
- GitHub: Pages is set to "Deploy from a branch", `main`, `/docs`. Pushes use the `gh` credential helper, so `gh auth status` must be logged in.
- This repo's commits use the GitHub noreply address (`git config user.email` here), because the repo is public.

## Gotchas learned

- The launchd agent is a run-and-exit job, so it uses `StartInterval` rather than `KeepAlive`; `KeepAlive` would relaunch it every ten seconds.
- Fatebook question links are `fatebook.io/q/<slug>--<id>` and the id is whatever follows the first `--`. A slug ending in `-` makes `---` and breaks the link, so the slug is trimmed after truncating.
- `getQuestions` returns forecasts as strings (`"0.35"`) and includes everyone's forecasts and my private tags on each question; the filter in `build.py` is the only thing keeping those off the public page.
- "Shared publicly" on Fatebook defaults to unlisted (link-only). 33 of my 85 shared questions were link-only when this was built.
- `build.py` refuses to write an empty list: a bad key or an API change would otherwise blank the live page.
- The chart is drawn at the container's pixel width and redrawn on resize; a fixed-size SVG scaled down made the labels unreadable on a phone.
