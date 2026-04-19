#!/usr/bin/env bash
# build.sh — builds a standalone macOS .app bundle
# Output: dist/sspath.app  (drag to /Applications to install)
# Run from anywhere: bash mac/build.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_SCRIPT="$SCRIPT_DIR/../sspath.py"

echo "=== sspath macOS build ==="
echo

if ! command -v python3 &>/dev/null; then
    echo "Error: python3 not found."
    exit 1
fi

if [ ! -f "$ROOT_SCRIPT" ]; then
    echo "Error: sspath.py not found at $ROOT_SCRIPT"
    exit 1
fi

echo "[1/2] Installing build dependencies..."
python3 -m pip install --quiet Pillow pystray pyobjc pyinstaller

echo "[2/2] Building sspath.app with PyInstaller..."
python3 -m PyInstaller \
    --onefile \
    --windowed \
    --name sspath \
    --hidden-import PIL \
    --hidden-import pystray \
    --hidden-import AppKit \
    --hidden-import Foundation \
    --hidden-import objc \
    "$ROOT_SCRIPT"

# Set LSUIElement so the app doesn't appear in the Dock (menu-bar only)
PLIST="dist/sspath.app/Contents/Info.plist"
if [ -f "$PLIST" ]; then
    /usr/libexec/PlistBuddy -c "Add :LSUIElement bool true" "$PLIST" 2>/dev/null \
        || /usr/libexec/PlistBuddy -c "Set :LSUIElement true" "$PLIST"
    echo "Set LSUIElement=true (hides from Dock)"
fi

echo
echo "Build complete: dist/sspath.app"
echo "  To install: drag dist/sspath.app to /Applications"
echo "  To run now: open dist/sspath.app"
