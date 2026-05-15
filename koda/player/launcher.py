import subprocess, os
import shutil
from pathlib import Path


def find_player(player: str = "mpv") -> str | None:
    """
    Ищет исполняемый файл плеера.
    Сначала проверяет PATH, затем типичные пути на Windows.
    """
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


def _build_args(exe: str, url: str, title: str, start_from: float) -> list[str]:
    """Строит аргументы под конкретный плеер."""
    name = Path(exe).stem.lower()

    if "vlc" in name:
        args = [exe, url]
        if title:
            args += ["--meta-title", title]
        if start_from > 0:
            args += [f"--start-time={start_from}"]
    else:
        args = [exe, url]
        if title:
            args += [f"--title={title}"]
        if start_from > 0:
            args += [f"--start={start_from}"]

    return args


def play(
    url: str,
    player: str = "mpv",
    title: str = "",
    start_from: float = 0.0,  # секунды
) -> None:
    """
    Открывает поток в mpv.

    :param url:        прямая ссылка на .m3u8
    :param player:     имя или путь к плееру
    :param title:      название (показывается в заголовке окна mpv)
    :param start_from: начать с этого таймкода (в секундах)
    """
    exe = find_player(player)
    if not exe:
        raise FileNotFoundError(
            f"Плеер '{player}' не найден. "
            "Установи mpv: https://mpv.io/installation/"
        )

    args = _build_args(exe, url, title, start_from)

    if title:
        args += [f"--title={title}"]

    if start_from > 0:
        args += [f"--start={start_from}"]

    subprocess.run(args, check=False,
                   stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)