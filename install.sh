#!/usr/bin/env bash
# install.sh — installs sspath on Linux
# Run from the project directory: bash install.sh

set -e

INSTALL_DIR="$HOME/.local/share/sspath"
BIN_DIR="$HOME/.local/bin"
AUTOSTART_DIR="$HOME/.config/autostart"
APP_DIR="$HOME/.local/share/applications"

echo "=== sspath installer ==="
echo

# ── System dependencies ────────────────────────────────────────────────────────

echo "[1/4] Installing system dependencies..."
sudo apt-get install -y python3 python3-venv python3-tk

# AppIndicator GIR — lets pystray use the native GNOME top-panel protocol
sudo apt-get install -y gir1.2-ayatanaappindicator3-0.1 2>/dev/null \
    || sudo apt-get install -y gir1.2-appindicator3-0.1 2>/dev/null \
    || echo "  Note: AppIndicator GIR not found; tray icon may not appear in GNOME top panel"

# Clipboard tool
if [ -n "$WAYLAND_DISPLAY" ] || [ "$XDG_SESSION_TYPE" = "wayland" ]; then
    sudo apt-get install -y wl-clipboard
    echo "  Clipboard: Wayland (wl-clipboard)"
else
    sudo apt-get install -y xclip
    echo "  Clipboard: X11 (xclip)"
fi

# ── Copy script + create venv ──────────────────────────────────────────────────

echo "[2/4] Setting up sspath environment in $INSTALL_DIR ..."
mkdir -p "$INSTALL_DIR"
cp sspath.py "$INSTALL_DIR/sspath.py"

python3 -m venv "$INSTALL_DIR/.venv"
"$INSTALL_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$INSTALL_DIR/.venv/bin/pip" install --quiet Pillow pystray

# ── Launcher script ────────────────────────────────────────────────────────────

echo "[3/4] Creating launcher at $BIN_DIR/sspath ..."
mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/sspath" << EOF
#!/usr/bin/env bash
exec "$INSTALL_DIR/.venv/bin/python" "$INSTALL_DIR/sspath.py" "\$@"
EOF
chmod +x "$BIN_DIR/sspath"

# ── Desktop entries (autostart + app launcher) ─────────────────────────────────

echo "[4/4] Registering desktop entries..."
mkdir -p "$AUTOSTART_DIR" "$APP_DIR"

# Autostart — launches sspath at login
cat > "$AUTOSTART_DIR/sspath.desktop" << EOF
[Desktop Entry]
Type=Application
Name=sspath
Comment=Screenshot Path Interceptor
Exec=$BIN_DIR/sspath
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
EOF

# App launcher — shows up in GNOME Activities / app grid
cat > "$APP_DIR/sspath.desktop" << EOF
[Desktop Entry]
Type=Application
Name=sspath
Comment=Screenshot Path Interceptor
Exec=$BIN_DIR/sspath
Terminal=false
Categories=Utility;
EOF

# Update desktop database
update-desktop-database "$APP_DIR" 2>/dev/null || true

echo
echo "Done!"
echo "  Run now:       sspath"
echo "  Auto-starts:   on next login"
echo "  App launcher:  search 'sspath' in GNOME Activities"
echo "  Uninstall:     bash uninstall.sh"
