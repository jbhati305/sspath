"""sspath.py — Screenshot Path Interceptor

When enabled, intercepts screenshots and replaces the clipboard with the
file path to that screenshot, formatted for the active terminal.

Windows:
  - WSL terminal   → /mnt/c/Users/...
  - PowerShell/CMD → C:\\Users\\...
  - Unknown        → both paths (WSL on line 1, Windows on line 2)

Linux:
  - Always the native path: /home/user/Pictures/Screenshots/...
  - Supports X11 (xclip) and Wayland (wl-clipboard)

Handles two screenshot scenarios:
  1. Saved-to-file  → watches the Screenshots folder for new PNGs
  2. Clipboard-only → saves the image, then copies the path

Windows dependencies: pip install pywin32 Pillow pystray psutil
Linux dependencies:   pip install Pillow pystray
                      apt install xclip        (X11)
                      apt install wl-clipboard  (Wayland)
Run from native Python (not WSL on Windows).
"""

import atexit
import os
import sys
import hashlib
import subprocess
import threading
import getpass
from datetime import datetime
from pathlib import Path
from typing import Optional

import tkinter as tk
from PIL import Image, ImageDraw
import pystray

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")

if IS_WINDOWS:
    import ctypes
    import win32clipboard
    import win32con
    import win32gui
    import win32process
    import psutil
    from PIL import ImageGrab

# ── Constants ──────────────────────────────────────────────────────────────────

POLL_MS = 500

if IS_WINDOWS:
    USERNAME = os.environ.get("USERNAME") or getpass.getuser()
    SCREENSHOTS_DIR = Path(f"C:\\Users\\{USERNAME}\\Pictures\\Screenshots")
else:
    SCREENSHOTS_DIR = Path.home() / "Pictures" / "Screenshots"

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


def format_path(path: str, target: str) -> str:
    """Return path string appropriate for the detected terminal."""
    if IS_LINUX:
        return path  # always a native Linux path
    if target == "wsl":
        return to_wsl_path(path)
    if target == "windows":
        return path
    # unknown: provide both so the user can pick
    return f"{to_wsl_path(path)}\n{path}"


# ── Terminal detection ─────────────────────────────────────────────────────────

def detect_target_terminal() -> str:
    """
    Determine the terminal type in use.
    Linux always returns 'linux'.
    Windows inspects the foreground window's process tree.
    Returns 'wsl', 'windows', 'linux', or 'unknown'.
    """
    if IS_LINUX:
        return "linux"

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


# ── Display server (Linux) ─────────────────────────────────────────────────────

def _linux_display_server() -> str:
    """Returns 'wayland' or 'x11'."""
    if os.environ.get("WAYLAND_DISPLAY") or os.environ.get("XDG_SESSION_TYPE") == "wayland":
        return "wayland"
    return "x11"


# Cached once at startup — display server doesn't change while the app runs.
_DISPLAY_SERVER: str = _linux_display_server() if IS_LINUX else ""


# ── Wayland clipboard watcher (event-driven, replaces per-poll wl-paste) ──────

if IS_LINUX:
    _WAYLAND_FLAG = Path(f"/tmp/sspath_{os.getpid()}.flag")
    atexit.register(lambda: _WAYLAND_FLAG.unlink(missing_ok=True))

_wayland_flag_mtime: float = 0.0


def _start_wayland_watcher() -> Optional[subprocess.Popen]:
    """
    Start a single long-running `wl-paste --watch touch FLAG` process.
    It touches FLAG whenever the clipboard changes — no per-poll subprocess
    spawning needed.  Returns the Popen object so the caller can terminate it.
    """
    try:
        return subprocess.Popen(
            ["wl-paste", "--watch", "touch", str(_WAYLAND_FLAG)],
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        return None


def _wayland_flag_changed() -> bool:
    """True if the clipboard has changed since the last call (mtime check)."""
    global _wayland_flag_mtime
    try:
        mtime = _WAYLAND_FLAG.stat().st_mtime
        if mtime != _wayland_flag_mtime:
            _wayland_flag_mtime = mtime
            return True
    except FileNotFoundError:
        pass
    return False


def _x11_clipboard_has_image() -> bool:
    """Lightweight X11 pre-check: list MIME types without downloading content."""
    try:
        result = subprocess.run(
            ["xclip", "-selection", "clipboard", "-t", "TARGETS", "-o"],
            capture_output=True, timeout=2,
        )
        return b"image/" in result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# ── Clipboard helpers ──────────────────────────────────────────────────────────

def get_clipboard_image_bytes() -> Optional[bytes]:
    """
    Return raw image bytes if the clipboard contains an image, else None.
    Windows: reads CF_DIB.
    Linux: reads via xclip (X11) or wl-paste (Wayland).
    """
    if IS_WINDOWS:
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

    # Linux — only called after flag/type pre-check confirms something changed
    try:
        if _DISPLAY_SERVER == "wayland":
            cmd = ["wl-paste", "--no-newline", "--type", "image/png"]
        else:
            cmd = ["xclip", "-selection", "clipboard", "-t", "image/png", "-o"]
        result = subprocess.run(cmd, capture_output=True, timeout=2)
        if result.returncode == 0 and result.stdout:
            return result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def set_clipboard_text(text: str) -> None:
    """Write text to the system clipboard."""
    if IS_WINDOWS:
        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
        finally:
            win32clipboard.CloseClipboard()
        return

    # Linux
    try:
        cmd = ["wl-copy"] if _DISPLAY_SERVER == "wayland" else ["xclip", "-selection", "clipboard"]
        subprocess.run(cmd, input=text.encode(), check=True, timeout=2)
    except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
        pass


def save_clipboard_image() -> str:
    """
    Save the current clipboard image to the Screenshots folder as a PNG.
    Returns the path string of the saved file.
    """
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filepath = SCREENSHOTS_DIR / f"sspath_{timestamp}.png"

    if IS_WINDOWS:
        img = ImageGrab.grabclipboard()
        if img is None:
            raise RuntimeError("No image on clipboard")
        img.save(str(filepath), "PNG")
        return str(filepath)

    # Linux: re-use bytes already confirmed present by _watch_clipboard
    data = get_clipboard_image_bytes()
    if not data:
        raise RuntimeError("No image on clipboard")
    filepath.write_bytes(data)
    return str(filepath)



# ── App ────────────────────────────────────────────────────────────────────────

class SsPathApp:
    def __init__(self):
        self.enabled = False
        self.known_files: set = set()
        self.last_image_hash: Optional[str] = None
        self.last_terminal: str = "linux" if IS_LINUX else "unknown"
        self._wayland_watcher: Optional[subprocess.Popen] = None

        # Snapshot existing screenshots so we don't trigger on old files
        SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        self.known_files = {str(p) for p in SCREENSHOTS_DIR.glob("*.png")}

        if IS_WINDOWS:
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
        self.root.title("sspath")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self._quit)
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
            pystray.MenuItem("Quit", lambda icon, item: self.root.after(0, self._quit)),
        )
        self.tray = pystray.Icon("sspath", icon_img, "sspath - OFF", menu)
        threading.Thread(target=self.tray.run, daemon=True).start()

        # Wayland: start event-driven clipboard watcher (replaces per-poll wl-paste)
        if IS_LINUX and _DISPLAY_SERVER == "wayland":
            self._wayland_watcher = _start_wayland_watcher()

        # Start polling loop (stays on main thread via after())
        self.root.after(POLL_MS, self._poll)

    # ── UI ─────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.root.minsize(480, 220)
        frame = tk.Frame(self.root, padx=32, pady=24)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="sspath", font=("Segoe UI", 18, "bold")).pack()
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
            self.tray.title = "sspath - ON"
        else:
            self.btn.config(text="● OFF", bg="#c62828", activebackground="#b71c1c")
            self.status.set("Idle")
            self.tray.title = "sspath - OFF"

    def _hide(self):
        self.root.withdraw()

    def _show(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _quit(self, icon=None, item=None):
        if self._wayland_watcher is not None:
            self._wayland_watcher.terminate()
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
        """Remember the last foreground window that was a known terminal.
        On Windows: needed because Snipping Tool steals focus during Win+Shift+S.
        On Linux: always 'linux', so this is a no-op after initialisation."""
        result = detect_target_terminal()
        if result != "unknown":
            self.last_terminal = result

    def _watch_folder(self):
        """Detect new PNGs in the Screenshots folder (Win+PrtSc / DE screenshot shortcut)."""
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
        """Detect new clipboard images (clipboard-only screenshot tools)."""
        if IS_LINUX:
            if _DISPLAY_SERVER == "wayland":
                # Skip the expensive wl-paste call unless the watcher flagged a change
                if not _wayland_flag_changed():
                    return
            else:
                # X11: cheap TARGETS pre-check avoids downloading image data every poll
                if not _x11_clipboard_has_image():
                    self.last_image_hash = None
                    return

        data = get_clipboard_image_bytes()

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
            path = save_clipboard_image()
        except Exception as exc:
            self.status.set(f"Save error: {exc}")
            return

        # Tell the folder watcher to ignore this file we just created
        self.known_files.add(path)

        set_clipboard_text(format_path(path, self.last_terminal))
        self.status.set(f"[{self.last_terminal}] {Path(path).name}")
        # Clipboard now holds text, so next poll: get_clipboard_image_bytes() → None → hash resets

    def run(self):
        self.root.mainloop()
        # Ensure the process exits even if pystray's GTK loop lingers in its thread
        os._exit(0)


def main():
    app = SsPathApp()
    app.run()


if __name__ == "__main__":
    main()
