#!/bin/zsh
# Installs (or reinstalls) the hourly updater. Safe to rerun.
set -e
LABEL=com.elityre.prediction-dashboard
DEST=~/Library/LaunchAgents/$LABEL.plist
cp "$(dirname "$0")/$LABEL.plist" "$DEST"
launchctl bootout gui/$(id -u)/$LABEL 2>/dev/null || true
# bootout returns before the old job is fully gone; bootstrap fails if it is not.
for i in 1 2 3 4 5; do launchctl print gui/$(id -u)/$LABEL >/dev/null 2>&1 || break; sleep 1; done
launchctl bootstrap gui/$(id -u) "$DEST"
echo "installed $LABEL; log: ~/Library/Logs/prediction-dashboard.log"
