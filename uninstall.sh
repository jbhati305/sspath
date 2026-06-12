#!/usr/bin/env bash
# uninstall.sh — removes sspath from Linux

set -e

echo "=== sspath uninstaller ==="

rm -rf "$HOME/.local/share/sspath"
rm -f  "$HOME/.local/bin/sspath"
rm -f  "$HOME/.config/autostart/sspath.desktop"
rm -f  "$HOME/.local/share/applications/sspath.desktop"
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true

echo "sspath removed."
