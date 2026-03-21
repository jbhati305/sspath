# imgpath

**Takes a screenshot → puts the file path in your clipboard.**

No more dragging files or hunting through Explorer. imgpath watches for new screenshots and instantly replaces the clipboard image with the path to that file — formatted for whichever terminal you were just in.

---

## Download

Go to [Releases](../../releases) and download `imgpath.exe`. No Python required.

---

## What it does

| You do | imgpath does |
|---|---|
| Win + PrtSc | Detects the new file, copies its path |
| Win + Shift + S | Saves the clipboard image, copies its path |
| PrtSc / Alt + PrtSc | Saves the clipboard image, copies its path |

The path is formatted automatically based on your terminal:

| Terminal | Path you get |
|---|---|
| WSL | `/mnt/c/Users/you/Pictures/Screenshots/...` |
| PowerShell / CMD | `C:\Users\you\Pictures\Screenshots\...` |
| Unknown | Both formats, one per line — pick the one you need |

---

## Usage

1. Run `imgpath.exe`
2. Click **ON**
3. Take a screenshot — the path is already in your clipboard
4. Paste directly into your terminal

Closing the window sends imgpath to the system tray. It keeps running until you right-click the tray icon and select **Quit**.

Toggle **OFF** any time you want to take a normal screenshot without path conversion.

---

## Run from source

Requires Windows Python (not WSL).

```
pip install pywin32 Pillow pystray psutil
python imgpath.py
```

## Build the exe yourself

```
pip install pyinstaller
pyinstaller --onefile --windowed --hidden-import win32clipboard --hidden-import win32con --hidden-import win32gui --hidden-import win32process --collect-all win32 imgpath.py
```

Output is in `dist/imgpath.exe`.
