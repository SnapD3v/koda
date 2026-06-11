import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

import httpx

from koda import __version__

GITHUB_REPO = "SnapD3v/koda"
_API_URL    = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

_PLATFORM_ASSET: dict[str, str] = {
    "win32":  "koda.exe",
    "darwin": "koda-macos",
    "linux":  "koda-linux.AppImage",
}


async def check_update() -> str | None:
    """Returns the latest release tag if it differs from the current version,
    or None if already up-to-date or if the check fails."""
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(
                _API_URL,
                headers={"Accept": "application/vnd.github+json"},
                follow_redirects=True,
            )
        if r.status_code != 200:
            return None
        tag = r.json().get("tag_name", "")
        if tag and tag.lstrip("v") != __version__:
            return tag
    except Exception:
        pass
    return None


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def current_exe() -> Path | None:
    return Path(sys.executable) if is_frozen() else None


async def download_update(
    tag: str,
    on_progress: Callable[[int, int], None] | None = None,
) -> Path:
    """Download the release binary for the current platform to a temp file."""
    asset  = _PLATFORM_ASSET.get(sys.platform, "koda-linux.AppImage")
    url    = f"https://github.com/{GITHUB_REPO}/releases/download/{tag}/{asset}"
    suffix = ".exe" if sys.platform == "win32" else ""
    tmp    = Path(tempfile.gettempdir()) / f"koda_update{suffix}"
    async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
        async with client.stream("GET", url) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            done  = 0
            with open(tmp, "wb") as f:
                async for chunk in r.aiter_bytes(65536):
                    f.write(chunk)
                    done += len(chunk)
                    if on_progress:
                        on_progress(done, total)
    return tmp


def apply_update(src: Path) -> None:
    """Replace the current executable with src, then restart. Exits this process."""
    exe = current_exe()
    if exe is None:
        raise RuntimeError("Автообновление доступно только в собранном бинарнике")

    if sys.platform == "win32":
        bat = Path(tempfile.gettempdir()) / "koda_updater.bat"
        bat.write_text(
            "@echo off\n"
            ":wait\n"
            f'tasklist /fi "imagename eq koda.exe" | find /i "koda.exe" >nul\n'
            "if not errorlevel 1 (\n"
            "    timeout /t 1 /nobreak >nul\n"
            "    goto wait\n"
            ")\n"
            f'move /y "{src}" "{exe}"\n'
            f'start "" "{exe}"\n'
            'del "%~f0"\n',
            encoding="utf-8",
        )
        subprocess.Popen(
            ["cmd", "/c", str(bat)],
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        )
    else:
        src.replace(exe)
        exe.chmod(0o755)
        subprocess.Popen([str(exe)])

    sys.exit(0)
