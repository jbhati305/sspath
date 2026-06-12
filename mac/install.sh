#!/usr/bin/env bash
# install.sh — installs sspath on macOS
# Run from the mac/ directory: bash install.sh

set -e

INSTALL_DIR="$HOME/.local/share/sspath"
BIN_DIR="$HOME/.local/bin"
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"
PLIST="$LAUNCH_AGENTS/com.sspath.app.plist"

echo "=== sspath installer (macOS) ==="
echo

# ── Check Python ───────────────────────────────────────────────────────────────

if ! command -v python3 &>/dev/null; then
    echo "Error: python3 not found. Install from https://www.python.org or via Homebrew."
    exit 1
fi

PYTHON=$(command -v python3)
echo "Python: $PYTHON ($(python3 --version))"

# Check tkinter (missing with some Homebrew installs)
if ! python3 -c "import tkinter" 2>/dev/null; then
    echo
    echo "tkinter not found. Install it with:"
    echo "  brew install python-tk"
    echo "Then re-run this script."
    exit 1
fi

# ── Create venv + install deps ─────────────────────────────────────────────────

echo "[1/3] Setting up environment in $INSTALL_DIR ..."
mkdir -p "$INSTALL_DIR"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cp "$SCRIPT_DIR/../sspath.py" "$INSTALL_DIR/sspath.py"

python3 -m venv "$INSTALL_DIR/.venv"
"$INSTALL_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$INSTALL_DIR/.venv/bin/pip" install --quiet Pillow pystray pyobjc

# ── Launcher script ────────────────────────────────────────────────────────────

echo "[2/3] Creating launcher at $BIN_DIR/sspath ..."
mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/sspath" << EOF
#!/usr/bin/env bash
exec "$INSTALL_DIR/.venv/bin/python" "$INSTALL_DIR/sspath.py" "\$@"
EOF
chmod +x "$BIN_DIR/sspath"

# Ensure ~/.local/bin is in PATH
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo
    echo "Note: add ~/.local/bin to your PATH:"
    echo '  echo export PATH="$HOME/.local/bin:$PATH" >> ~/.zshrc && source ~/.zshrc'
fi

# ── LaunchAgent (autostart at login) ──────────────────────────────────────────

echo "[3/3] Registering LaunchAgent for autostart ..."
mkdir -p "$LAUNCH_AGENTS"
cat > "$PLIST" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.sspath.app</string>
    <key>ProgramArguments</key>
    <array>
        <string>$INSTALL_DIR/.venv/bin/python</string>
        <string>$INSTALL_DIR/sspath.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
    <key>StandardErrorPath</key>
    <string>$HOME/.local/share/sspath/sspath.log</string>
</dict>
</plist>
EOF

# Load it now without requiring a reboot
launchctl load "$PLIST" 2>/dev/null || true

echo
echo "Done!"
echo "  Run now:       sspath"
echo "  Auto-starts:   on next login (LaunchAgent registered)"
echo "  Logs:          ~/.local/share/sspath/sspath.log"
echo "  Uninstall:     bash uninstall.sh"
