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
