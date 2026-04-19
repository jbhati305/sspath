# PR 1 — Structure Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove redundant `mac/sspath.py`, fix `mac/build.sh` path reference, update README to reflect cross-platform support, and keep `requirements.txt` accurate.

**Architecture:** Pure file edits — no logic changes to `sspath.py`. Verification is done by confirming `uv run sspath` still resolves and the deleted file is gone.

**Tech Stack:** bash, uv, git

---

## File Map

| Action | File |
|--------|------|
| Delete | `mac/sspath.py` |
| Modify | `mac/build.sh` |
| Modify | `requirements.txt` |
| Rewrite | `README.md` |
| Verify (no change needed) | `mac/uninstall.sh` |

---

### Task 1: Delete `mac/sspath.py`

**Files:**
- Delete: `mac/sspath.py`

- [ ] **Step 1: Confirm `mac/install.sh` no longer references local `sspath.py`**

Run:
```bash
grep "sspath.py" mac/install.sh
```
Expected output:
```
cp "$SCRIPT_DIR/../sspath.py" "$INSTALL_DIR/sspath.py"
```
If the output shows `cp sspath.py` (without `$SCRIPT_DIR/../`), stop and fix `mac/install.sh` first.

- [ ] **Step 2: Delete the file**

```bash
rm mac/sspath.py
```

- [ ] **Step 3: Verify it's gone**

```bash
ls mac/
```
Expected: `build.sh  install.sh  uninstall.sh` — no `sspath.py`.

- [ ] **Step 4: Verify `uv run sspath` still resolves**

```bash
uv run python -c "import sspath; print('ok')"
```
Expected: `ok`

- [ ] **Step 5: Commit**

```bash
git add mac/sspath.py
git commit -m "remove redundant mac/sspath.py — root sspath.py handles all platforms"
```

---

### Task 2: Fix `mac/build.sh` to use root `sspath.py`

**Files:**
- Modify: `mac/build.sh`

- [ ] **Step 1: Add `SCRIPT_DIR` and update the PyInstaller call**

Replace the PyInstaller block in `mac/build.sh`. The full file should become:

```bash
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
```

- [ ] **Step 2: Verify the script is valid bash**

```bash
bash -n mac/build.sh
```
Expected: no output (no syntax errors).

- [ ] **Step 3: Commit**

```bash
git add mac/build.sh
git commit -m "fix mac/build.sh to reference root sspath.py"
```

---

### Task 3: Update `requirements.txt`

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Update the file**

Replace the entire contents of `requirements.txt` with:

```
# Reference only — dependencies are managed by uv via pyproject.toml.
# To install: uv sync
# To run:     uv run sspath

# All platforms
Pillow
pystray

# macOS only
pyobjc

# Windows only
pywin32
psutil

# Linux system packages (not pip-installable):
#   brew install python-tk          (macOS, if using Homebrew Python)
#   sudo apt install python3-tk     (Linux)
#   sudo apt install xclip          (Linux X11)
#   sudo apt install wl-clipboard   (Linux Wayland)
```

- [ ] **Step 2: Commit**

```bash
git add requirements.txt
git commit -m "update requirements.txt to include pyobjc for macOS"
```

---

### Task 4: Rewrite README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace README contents**

```markdown
# sspath

**Takes a screenshot → puts the file path in your clipboard.**

No more dragging files or hunting through Finder / File Explorer. sspath watches for new screenshots and instantly copies the file path to your clipboard. Created to streamline [Claude Code](https://claude.ai/code) workflow.

---

## What it does

| You do | sspath does |
|---|---|
| Cmd+Shift+3 / Cmd+Shift+4 | Detects the new file, copies its path |
| Cmd+Ctrl+Shift+3 / Cmd+Ctrl+Shift+4 | Saves the clipboard image, copies its path |
| Win+PrtSc | Detects the new file, copies its path |
| Win+Shift+S / PrtSc | Saves the clipboard image, copies its path |

---

## Install

### macOS

```bash
bash mac/install.sh
```

Requires Python 3.10+ with tkinter. If using Homebrew Python:
```bash
brew install python-tk
```

### Linux

```bash
bash install.sh
```

Requires: `python3-venv`, `python3-tk`, and either `xclip` (X11) or `wl-clipboard` (Wayland) — the installer handles these automatically on Debian/Ubuntu.

---

## Usage

1. Run `sspath` (or `uv run sspath` from source)
2. Click **ON**
3. Take a screenshot — the path is already in your clipboard
4. Paste directly into your terminal or editor

Closing the window sends sspath to the system tray. It keeps running until you right-click the tray icon and select **Quit**.

Toggle **OFF** any time you want a normal screenshot without path conversion.

---

## Run from source

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv run sspath
```

uv installs the right dependencies for your platform automatically — no manual `pip install` needed.

---

## Uninstall

```bash
# macOS
bash mac/uninstall.sh

# Linux
bash uninstall.sh
```
```

- [ ] **Step 2: Verify markdown renders cleanly (spot check)**

```bash
head -5 README.md
```
Expected: `# sspath` on line 1.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "rewrite README for cross-platform: macOS + Linux install, uv from source"
```

---

### Task 5: Verify `mac/uninstall.sh` (read-only check)

**Files:**
- Verify: `mac/uninstall.sh`

- [ ] **Step 1: Confirm it removes all three artefacts**

```bash
cat mac/uninstall.sh
```

Check that it contains all three of:
1. `launchctl unload "$PLIST"` — unloads the LaunchAgent
2. `rm -rf "$HOME/.local/share/sspath"` — removes the venv + script
3. `rm -f "$HOME/.local/bin/sspath"` — removes the launcher

Expected: all three are present. Current file already has them — no change needed.

- [ ] **Step 2: Final state check**

```bash
git status
```
Expected: `nothing to commit, working tree clean`

```bash
ls mac/
```
Expected: `build.sh  install.sh  uninstall.sh`

- [ ] **Step 3: Push branch**

```bash
git push -u origin cleanup/structure
```

---

## Done

PR 1 is complete. Next: check out `fix/core-macos` from this branch and write/execute plan `2026-04-20-pr2-core-macos.md`.
