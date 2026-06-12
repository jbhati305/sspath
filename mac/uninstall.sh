#!/usr/bin/env bash
# uninstall.sh — removes sspath from macOS

set -e

PLIST="$HOME/Library/LaunchAgents/com.sspath.app.plist"

echo "=== sspath uninstaller (macOS) ==="

# Unload LaunchAgent before deleting the plist
launchctl unload "$PLIST" 2>/dev/null || true

rm -rf "$HOME/.local/share/sspath"
rm -f  "$HOME/.local/bin/sspath"
rm -f  "$PLIST"

echo "sspath removed."
