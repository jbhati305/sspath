"""imgpath.py — Screenshot Path Interceptor

When enabled, intercepts screenshots and replaces the clipboard with the
file path to that screenshot, formatted for the active terminal:
  - WSL terminal  → /mnt/c/Users/...
  - PowerShell/CMD → C:\\Users\\...
  - Unknown        → both paths (WSL on line 1, Windows on line 2)

Handles two screenshot scenarios:
  1. Win+PrtSc      → file auto-saved to Pictures\\Screenshots; watches folder
  2. Win+Shift+S /
     PrtSc /
     Alt+PrtSc      → image goes to clipboard only; saves it, then copies path

Dependencies: pip install pywin32 Pillow pystray psutil
Run from Windows Python (not WSL).
"""

import os
import hashlib
import threading
import getpass
import ctypes
from datetime import datetime
from pathlib import Path
from typing import Optional

import tkinter as tk
import win32clipboard
import win32con
import win32gui
import win32process
import psutil
from PIL import Image, ImageDraw, ImageGrab
import pystray

# ── Constants ──────────────────────────────────────────────────────────────────

USERNAME = os.environ.get("USERNAME") or getpass.getuser()
SCREENSHOTS_DIR = Path(f"C:\\Users\\{USERNAME}\\Pictures\\Screenshots")
POLL_MS = 500

WSL_PROCS = {
    "wsl.exe", "bash.exe", "ubuntu.exe", "debian.exe", "kali.exe",
    "ubuntu2004.exe", "ubuntu2204.exe", "ubuntu2404.exe",
    "opensuse-42.exe", "sles-12.exe",
}
WIN_PROCS = {"powershell.exe", "pwsh.exe", "cmd.exe"}


# ── Path utilities ─────────────────────────────────────────────────────────────

def to_wsl_path(win_path: str) -> str:
    """Convert C:\\Users\\... → /mnt/c/Users/..."""
    p = win_path.replace("\\", "/")
    if len(p) >= 2 and p[1] == ":":
        drive = p[0].lower()
        p = f"/mnt/{drive}{p[2:]}"
    return p


def format_path(win_path: str, target: str) -> str:
    """Return path string appropriate for the detected terminal."""
    if target == "wsl":
        return to_wsl_path(win_path)
    if target == "windows":
        return win_path
    # unknown: provide both so the user can pick
    return f"{to_wsl_path(win_path)}\n{win_path}"


# ── Terminal detection ─────────────────────────────────────────────────────────

def detect_target_terminal() -> str:
    """
    Inspect the foreground window's process to determine terminal type.
    Returns 'wsl', 'windows', or 'unknown'.
    """
    try:
        hwnd = win32gui.GetForegroundWindow()
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        proc = psutil.Process(pid)
        name = proc.name().lower()

        if name in WSL_PROCS:
            return "wsl"
        if name in WIN_PROCS:
            return "windows"
        if name == "windowsterminal.exe":
            # Windows Terminal hosts multiple panes; check children for WSL
            try:
                for child in proc.children(recursive=True):
                    if child.name().lower() in WSL_PROCS:
                        return "wsl"
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            return "windows"
    except Exception:
        pass
    return "unknown"


# ── Clipboard helpers ──────────────────────────────────────────────────────────

def get_clipboard_dib() -> Optional[bytes]:
    """Return raw CF_DIB bytes if the clipboard contains an image, else None."""
    try:
        win32clipboard.OpenClipboard()
        try:
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_DIB):
                return win32clipboard.GetClipboardData(win32con.CF_DIB)
        finally:
            win32clipboard.CloseClipboard()
    except Exception:
        pass
    return None


def set_clipboard_text(text: str) -> None:
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
    finally:
        win32clipboard.CloseClipboard()


def save_clipboard_image() -> str:
    """
    Save the current clipboard image to the Screenshots folder as a PNG.
    Returns the Windows path string of the saved file.
    """
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filepath = SCREENSHOTS_DIR / f"imgpath_{timestamp}.png"
    img = ImageGrab.grabclipboard()
    if img is None:
        raise RuntimeError("No image on clipboard")
    img.save(str(filepath), "PNG")
    return str(filepath)


# ── App ────────────────────────────────────────────────────────────────────────

class ImgPathApp:
    def __init__(self):
        self.enabled = False
        self.known_files: set = set()
        self.last_image_hash: Optional[str] = None
        self.last_terminal: str = "unknown"  # tracks last active terminal window

        # Snapshot existing screenshots so we don't trigger on old files
        SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        self.known_files = {str(p) for p in SCREENSHOTS_DIR.glob("*.png")}

        # DPI awareness — must be called before Tk() so Windows scales correctly
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor DPI aware
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

        # Tkinter window
        self.root = tk.Tk()
        self.root.title("imgpath")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self._hide)
        self._build_ui()

        # System tray (runs on a daemon thread)
        icon_img = self._make_tray_icon()
        menu = pystray.Menu(
            pystray.MenuItem(
                "Toggle ON/OFF",
                lambda icon, item: self.root.after(0, self._toggle),
            ),
            pystray.MenuItem(
                "Show Window",
                lambda icon, item: self.root.after(0, self._show),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._quit),
        )
        self.tray = pystray.Icon("imgpath", icon_img, "imgpath — OFF", menu)
        threading.Thread(target=self.tray.run, daemon=True).start()

        # Start polling loop (stays on main thread via after())
        self.root.after(POLL_MS, self._poll)

    # ── UI ─────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.root.minsize(480, 220)
        frame = tk.Frame(self.root, padx=32, pady=24)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="imgpath", font=("Segoe UI", 18, "bold")).pack()
        tk.Label(
            frame,
            text="Screenshot → clipboard path",
            font=("Segoe UI", 11),
            fg="#777",
        ).pack(pady=(4, 18))

        self.btn = tk.Button(
            frame,
            text="● OFF",
            font=("Segoe UI", 13, "bold"),
            width=12,
            height=2,
            command=self._toggle,
            bg="#c62828",
            fg="white",
            activebackground="#b71c1c",
            relief="flat",
            cursor="hand2",
            bd=0,
        )
        self.btn.pack()

        self.status = tk.StringVar(value="Idle")
        tk.Label(
            frame,
            textvariable=self.status,
            font=("Segoe UI", 9),
            fg="#888",
            wraplength=420,
            justify="center",
        ).pack(pady=(14, 0))

    def _toggle(self):
        self.enabled = not self.enabled
        if self.enabled:
            self.btn.config(text="● ON", bg="#2e7d32", activebackground="#1b5e20")
            self.status.set("Monitoring...")
            self.tray.title = "imgpath — ON"
        else:
            self.btn.config(text="● OFF", bg="#c62828", activebackground="#b71c1c")
            self.status.set("Idle")
            self.tray.title = "imgpath — OFF"

    def _hide(self):
        self.root.withdraw()

    def _show(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _quit(self, icon=None, item=None):
        self.tray.stop()
        self.root.after(0, self.root.destroy)

    @staticmethod
    def _make_tray_icon() -> Image.Image:
        """Create a simple 64×64 tray icon (dark blue with white 'i')."""
        img = Image.new("RGB", (64, 64), "#1a237e")
        d = ImageDraw.Draw(img)
        d.ellipse([22, 6, 42, 26], fill="white")   # dot of 'i'
        d.rectangle([22, 32, 42, 58], fill="white") # stem of 'i'
        return img

    # ── Polling ────────────────────────────────────────────────────────────────

    def _poll(self):
        try:
            self._track_terminal()   # always update last known terminal
            self._watch_folder()
            self._watch_clipboard()
        except Exception as exc:
            self.status.set(f"Error: {exc}")
        self.root.after(POLL_MS, self._poll)

    def _track_terminal(self):
        """Continuously remember the last foreground window that was a known terminal.
        We store this so that when the Snipping Tool takes focus during Win+Shift+S,
        we still know which terminal the user was in beforehand."""
        result = detect_target_terminal()
        if result != "unknown":
            self.last_terminal = result

    def _watch_folder(self):
        """Detect new PNGs in the Screenshots folder (Win+PrtSc scenario)."""
        try:
            current = {str(p) for p in SCREENSHOTS_DIR.glob("*.png")}
        except Exception:
            return

        new = current - self.known_files
        self.known_files = current  # always update, even if disabled

        if not new or not self.enabled:
            return

        # If multiple files appeared at once, use the most recently modified
        newest = max(new, key=lambda p: Path(p).stat().st_mtime)
        set_clipboard_text(format_path(newest, self.last_terminal))
        self.status.set(f"[{self.last_terminal}] {Path(newest).name}")

    def _watch_clipboard(self):
        """Detect new clipboard images (Win+Shift+S / PrtSc / Alt+PrtSc scenario)."""
        data = get_clipboard_dib()

        if data is None:
            self.last_image_hash = None
            return

        h = hashlib.md5(data).hexdigest()
        if h == self.last_image_hash:
            return  # same image, already handled

        self.last_image_hash = h  # track even when disabled, to avoid stale triggers

        if not self.enabled:
            return

        try:
            win_path = save_clipboard_image()
        except Exception as exc:
            self.status.set(f"Save error: {exc}")
            return

        # Tell the folder watcher to ignore this file we just created
        self.known_files.add(win_path)

        set_clipboard_text(format_path(win_path, self.last_terminal))
        self.status.set(f"[{self.last_terminal}] {Path(win_path).name}")
        # Clipboard now holds text, so next poll: get_clipboard_dib() → None → hash resets

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = ImgPathApp()
    app.run()
