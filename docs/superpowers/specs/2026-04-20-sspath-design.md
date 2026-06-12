# sspath — Proper Cross-Platform Tool Design

**Date:** 2026-04-20
**Branch:** adding-linux-support
**Scope:** Structure cleanup → core improvements → CI/CD and distribution

---

## Overview

sspath is a system-tray utility that watches for new screenshots and copies the file path to the clipboard. It started as a Windows-only `.exe`, was extended to Linux and macOS, and is now being made into a properly structured, distributable cross-platform tool.

**Target platforms for releases:** macOS and Linux.
**Windows:** code remains functional but no release artifacts produced.

---

## Section 1: Project Structure Cleanup

### Goal
Remove redundancy, fix documentation, and make `uv run sspath` the canonical way to run from source.

### Changes

**Delete `mac/sspath.py`**
The root `sspath.py` now handles all three platforms with `IS_MAC`, `IS_LINUX`, `IS_WINDOWS` guards. `mac/sspath.py` is redundant and will be removed.

**Update `mac/build.sh`**
Currently references its own local `sspath.py`. Update to reference `../sspath.py` (matching the fix already applied to `mac/install.sh`).

**Rewrite README**
- Remove "Windows only" and `.exe` download references
- Add install instructions for macOS (`bash mac/install.sh`) and Linux (`bash install.sh`)
- Add "Run from source" section: `uv run sspath`
- Add platform requirements table (Python, tkinter, pyobjc on macOS)

**Update `requirements.txt`**
Add `pyobjc` under the macOS section. This file is comment-only (not used by uv) but should stay accurate.

**Verify `mac/uninstall.sh`**
Confirm it removes the LaunchAgent plist and `~/.local/share/sspath` correctly. The Linux `uninstall.sh` at root handles the `.desktop` files.

### What stays the same in this PR
`install.sh` (Linux), `mac/install.sh`, `sspath.py`. `pyproject.toml` gets dev dependencies added in Section 3.

---

## Section 2: Core Functionality Improvements

### Goal
Fix macOS-specific bugs and make the app robust against edge cases.

### Changes

**macOS screenshot directory fallback chain**
Current: `defaults read` → `~/Desktop`
New: `defaults read` → `~/Pictures/Screenshots` (if dir exists) → `~/Desktop`
Reason: macOS 14+ uses `~/Pictures/Screenshots` as the default, so the old fallback skips it.

**Defensive clipboard handling on macOS**
`ImageGrab.grabclipboard()` can raise on some macOS clipboard states (e.g. file references, native objects). Currently the exception propagates to the status bar. Fix: catch all exceptions in `get_clipboard_image_bytes()`, reset `last_image_hash = None` on failure, and return `None` silently.

**Tray icon ON/OFF state on macOS**
`pystray` on macOS silently ignores `.title` property updates. Current code sets `self.tray.title = "sspath - ON/OFF"` — this works on Linux/Windows but is a no-op on macOS. Fix: update the tray menu's first item to show the current state instead, so macOS users can tell if it's active.

**Missing pyobjc startup check**
If `pyobjc` is absent on macOS, `pystray` fails with a cryptic import error. Add a startup guard: on macOS, try `import AppKit` and show a clear error message with `pip install pyobjc` (or `uv sync` if using uv) if it fails, before tkinter initialises.

**Poll interval:** stays at 500ms — no change needed.

**Out of scope:** config files, custom save directories, system notifications.

---

## Section 3: Distribution / CI/CD

### Goal
Automated CI on every push, automated release artifacts on version tags.

### Workflows

**`.github/workflows/ci.yml`** — triggers on push and PRs to `main`:
- Install uv
- `uv sync`
- Lint: `uv run ruff check .`
- Smoke test: `python -c "import sspath"` (matrix: ubuntu-latest, macos-latest)

**`.github/workflows/release.yml`** — triggers on `v*` tags:
- **macOS runner:**
  - `uv sync && uv run pyinstaller --onefile --windowed --name sspath sspath.py`
  - Package `dist/sspath.app` into `sspath-macos.dmg` via `hdiutil`
  - Upload as release artifact
- **Linux runner:**
  - `uv sync && uv run pyinstaller --onefile --name sspath sspath.py`
  - Package `dist/sspath` into `sspath-linux.deb` via `dpkg-deb` and `sspath-linux.tar.gz`
  - Upload both as release artifacts
- Create GitHub Release with all artifacts attached

### Versioning
Bump `version` in `pyproject.toml`, commit, then:
```
git tag v0.2.0 && git push --tags
```
Release workflow fires automatically.

### New dev dependencies
```toml
[dependency-groups]
dev = [
    "ruff",
    "pyinstaller",
]
```

### Out of scope
Homebrew formula, code signing / macOS notarization, Windows `.exe` releases.

---

## Implementation Order

1. **PR 1 — Structure cleanup:** delete `mac/sspath.py`, update `mac/build.sh`, rewrite README, fix `requirements.txt`
2. **PR 2 — Core fixes:** macOS fallback chain, defensive clipboard, tray state, pyobjc startup check
3. **PR 3 — CI/CD:** `ci.yml`, `release.yml`, add dev dependencies, tag v0.2.0

Each PR is independently mergeable and reviewable.
