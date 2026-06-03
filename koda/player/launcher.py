import os
import subprocess
import shutil
import sys
import time
from pathlib import Path

WATCH_LATER_DIR = Path.home() / ".config" / "koda" / "watch_later"


def _find_oscc() -> bool:
    candidates = [
        Path.home() / ".config" / "mpv" / "scripts" / "oscc.lua",
        Path(os.environ.get("APPDATA", "")) / "mpv" / "scripts" / "oscc.lua",
    ]
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys._MEIPASS) / "mpv" / "scripts" / "oscc.lua")
    else:
        try:
            candidates.append(Path(sys.executable).parent / "mpv" / "scripts" / "oscc.lua")
        except Exception:
            pass
    return any(p.exists() for p in candidates)


def find_player(player: str = "mpv") -> str | None:
    # Bundled mpv inside a PyInstaller single-file build
    if getattr(sys, "frozen", False) and player == "mpv":
        bundled = Path(sys._MEIPASS) / "mpv" / "mpv.exe"
        if bundled.exists():
            return str(bundled)

    if path := shutil.which(player):
        return path

    windows_paths = [
        Path(r"C:\Program Files\mpv\mpv.exe"),
        Path(r"C:\Program Files (x86)\mpv\mpv.exe"),
        Path.home() / "scoop" / "apps" / "mpv" / "current" / "mpv.exe",
    ]
    for p in windows_paths:
        if p.exists():
            return str(p)

    return None


def _build_args(exe: str, url: str, title: str, start_from: float, oscc_title: str = "") -> list[str]:
    name = Path(exe).stem.lower()

    if "vlc" in name:
        args = [exe, url]
        if title:
            args += ["--meta-title", title]
        if start_from > 0:
            args += [f"--start-time={start_from}"]
    else:
        args = [
            exe, url,
            "--cache=yes",
            "--cache-pause=no",
            "--hwdec=auto-safe",
        ]
        if title:
            args += [f"--title={title}"]
        if start_from > 0:
            args += [f"--start={start_from}"]
        if oscc_title and _find_oscc():
            args += [f"--script-opts=oscc-title={oscc_title}"]

    return args


def _read_timecode_after(launch_time: float) -> float:
    """Parse start= from the watch-later file written most recently after launch_time."""
    try:
        candidates = [
            f for f in WATCH_LATER_DIR.glob("*")
            if f.stat().st_mtime > launch_time
        ]
        if not candidates:
            return 0.0
        newest = max(candidates, key=lambda f: f.stat().st_mtime)
        for line in newest.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith("start="):
                return float(line.partition("=")[2])
    except Exception:
        pass
    return 0.0


def play(
    url: str,
    player: str = "mpv",
    title: str = "",
    start_from: float = 0.0,
    oscc_title: str = "",
) -> float:
    """
    Opens the stream in the player. Blocks until the player exits.
    Returns the timecode (seconds) where playback stopped, or 0.0 if unknown.
    """
    exe = find_player(player)
    if not exe:
        raise FileNotFoundError(
            f"Плеер '{player}' не найден. "
            "Установи mpv: https://mpv.io/installation/"
        )

    WATCH_LATER_DIR.mkdir(parents=True, exist_ok=True)
    args = _build_args(exe, url, title, start_from, oscc_title)

    if "vlc" not in Path(exe).stem.lower():
        args += [
            "--input-terminal=no",  # don't read escape codes from the shared terminal stdin
            "--save-position-on-quit",
            f"--watch-later-dir={WATCH_LATER_DIR}",
        ]

    launch_time = time.time()
    subprocess.run(args, check=False,
                   stdin=subprocess.DEVNULL,   # cut off Textual's mouse-tracking bytes
                   stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)

    return _read_timecode_after(launch_time)
