"""sspath.py — Screenshot Path Interceptor (macOS)

When enabled, intercepts screenshots and replaces the clipboard with the
file path to that screenshot.

Two screenshot scenarios are handled:
  1. Saved to file (Cmd+Shift+3 / Cmd+Shift+4)  → folder watcher
  2. Clipboard-only (Cmd+Ctrl+Shift+3 / Cmd+Ctrl+Shift+4) → clipboard watcher

Dependencies: pip install Pillow pystray pyobjc
              brew install python-tk  (if using Homebrew Python)
"""

import hashlib
import io
import os
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

import tkinter as tk
from PIL import Image, ImageDraw, ImageGrab
import pystray

# ── Constants ──────────────────────────────────────────────────────────────────

POLL_MS = 500

def _default_screenshots_dir() -> Path:
    """
    Return the directory macOS saves screenshots to.
    Reads the user's preference from `defaults`; falls back to ~/Desktop.
    """
    try:
        result = subprocess.run(
            ["defaults", "read", "com.apple.screencapture", "location"],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode == 0:
            p = Path(result.stdout.strip()).expanduser()
            if p.is_dir():
                return p
    except Exception:
        pass
    return Path.home() / "Desktop"

SCREENSHOTS_DIR = _default_screenshots_dir()


# ── Clipboard helpers ──────────────────────────────────────────────────────────

def get_clipboard_image_bytes() -> Optional[bytes]:
    """
    Return PNG bytes if the clipboard contains an image, else None.
    Uses PIL's native macOS clipboard integration — no subprocess needed.
    """
    try:
        img = ImageGrab.grabclipboard()
        if not isinstance(img, Image.Image):
            return None
        buf = io.BytesIO()
        img.save(buf, "PNG")
        return buf.getvalue()
    except Exception:
        return None


def set_clipboard_text(text: str) -> None:
    """Write text to the macOS clipboard via pbcopy."""
    try:
        subprocess.run(["pbcopy"], input=text.encode(), check=True, timeout=2)
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        pass


def save_clipboard_image() -> str:
    """Save the clipboard image to SCREENSHOTS_DIR. Returns the file path."""
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filepath = SCREENSHOTS_DIR / f"sspath_{timestamp}.png"
    img = ImageGrab.grabclipboard()
    if not isinstance(img, Image.Image):
        raise RuntimeError("No image on clipboard")
    img.save(str(filepath), "PNG")
    return str(filepath)


# ── App ────────────────────────────────────────────────────────────────────────

class SsPathApp:
    def __init__(self):
        self.enabled = False
        self.known_files: set = set()
        self.last_image_hash: Optional[str] = None

        SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        self.known_files = {str(p) for p in SCREENSHOTS_DIR.glob("*.png")}

        self.root = tk.Tk()
        self.root.title("sspath")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self._quit)
        self._build_ui()

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

        self.root.after(POLL_MS, self._poll)

    # ── UI ─────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.root.minsize(480, 220)
        frame = tk.Frame(self.root, padx=32, pady=24)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="sspath", font=("Helvetica Neue", 18, "bold")).pack()
        tk.Label(
            frame,
            text="Screenshot -> clipboard path",
            font=("Helvetica Neue", 11),
            fg="#777",
        ).pack(pady=(4, 18))

        self.btn = tk.Button(
            frame,
            text="● OFF",
            font=("Helvetica Neue", 13, "bold"),
            width=12,
            height=2,
            command=self._toggle,
            bg="#c62828",
            fg="white",
            activebackground="#b71c1c",
            relief="flat",
            cursor="pointinghand",
            bd=0,
        )
        self.btn.pack()

        self.status = tk.StringVar(value="Idle")
        tk.Label(
            frame,
            textvariable=self.status,
            font=("Helvetica Neue", 9),
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

    def _show(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _quit(self, icon=None, item=None):
        self.tray.stop()
        self.root.after(0, self.root.destroy)

    @staticmethod
    def _make_tray_icon() -> Image.Image:
        """64x64 RGBA icon with transparent background for macOS menu bar."""
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.ellipse([4, 4, 60, 60], fill="#1a237e")
        d.ellipse([22, 6, 42, 26], fill="white")   # dot of 'i'
        d.rectangle([22, 32, 42, 58], fill="white") # stem of 'i'
        return img

    # ── Polling ────────────────────────────────────────────────────────────────

    def _poll(self):
        try:
            self._watch_folder()
            self._watch_clipboard()
        except Exception as exc:
            self.status.set(f"Error: {exc}")
        self.root.after(POLL_MS, self._poll)

    def _watch_folder(self):
        """Detect screenshots saved to disk (Cmd+Shift+3 / Cmd+Shift+4)."""
        try:
            current = {str(p) for p in SCREENSHOTS_DIR.glob("*.png")}
        except Exception:
            return

        new = current - self.known_files
        self.known_files = current

        if not new or not self.enabled:
            return

        newest = max(new, key=lambda p: Path(p).stat().st_mtime)
        set_clipboard_text(newest)
        self.status.set(Path(newest).name)

    def _watch_clipboard(self):
        """Detect clipboard-only screenshots (Cmd+Ctrl+Shift+3 / Cmd+Ctrl+Shift+4)."""
        data = get_clipboard_image_bytes()

        if data is None:
            self.last_image_hash = None
            return

        h = hashlib.md5(data).hexdigest()
        if h == self.last_image_hash:
            return  # same image already handled

        self.last_image_hash = h  # track even when disabled, to avoid stale triggers

        if not self.enabled:
            return

        try:
            path = save_clipboard_image()
        except Exception as exc:
            self.status.set(f"Save error: {exc}")
            return

        self.known_files.add(path)
        set_clipboard_text(path)
        self.status.set(Path(path).name)
        # Clipboard now holds text, so next poll: get_clipboard_image_bytes() → None

    def run(self):
        self.root.mainloop()
        os._exit(0)


def main():
    app = SsPathApp()
    app.run()


if __name__ == "__main__":
    main()
