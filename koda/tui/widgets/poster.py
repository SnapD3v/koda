"""Terminal poster widget.

Protocol priority: kitty → sixel → chafa → none (widget not shown).
"""

import base64
import io
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import httpx
from textual import work
from textual.widgets import Static


def _detect_protocol() -> str:
    term         = os.environ.get("TERM", "")
    term_program = os.environ.get("TERM_PROGRAM", "")
    if os.environ.get("KITTY_WINDOW_ID") or term == "xterm-kitty":
        return "kitty"
    if (
        "sixel" in term
        or term_program in ("iTerm.app", "WezTerm")
        or os.environ.get("TERM_PROGRAM_VERSION", "").startswith("WezTerm")
    ):
        return "sixel"
    if shutil.which("chafa"):
        return "chafa"
    return "none"


_PROTOCOL = _detect_protocol()


def _kitty_render(png_bytes: bytes, cols: int = 20, rows: int = 10) -> str:
    b64 = base64.standard_b64encode(png_bytes).decode()
    chunks = [b64[i:i + 4096] for i in range(0, len(b64), 4096)]
    parts: list[str] = []
    for idx, chunk in enumerate(chunks):
        m = 1 if idx < len(chunks) - 1 else 0
        ctrl = f"a=T,f=100,c={cols},r={rows},m={m}" if idx == 0 else f"m={m}"
        parts.append(f"\033_G{ctrl};{chunk}\033\\")
    return "".join(parts)


def _sixel_render(png_bytes: bytes, width: int = 160) -> str | None:
    try:
        from PIL import Image  # type: ignore
        img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
        scale = width / img.width
        img = img.resize((width, int(img.height * scale)), Image.LANCZOS)

        if shutil.which("img2sixel"):
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                img.save(f.name)
                tmp = f.name
            try:
                result = subprocess.run(
                    ["img2sixel", "-w", str(width), tmp],
                    capture_output=True, timeout=5,
                )
                return result.stdout.decode("utf-8", errors="replace")
            finally:
                Path(tmp).unlink(missing_ok=True)
    except Exception:
        pass
    return None


def _chafa_render(png_bytes: bytes, cols: int = 20, rows: int = 10) -> str | None:
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(png_bytes)
            tmp = f.name
        result = subprocess.run(
            ["chafa", f"--size={cols}x{rows}", "--animate=false", tmp],
            capture_output=True, timeout=5,
        )
        return result.stdout.decode("utf-8", errors="replace")
    except Exception:
        return None
    finally:
        if tmp:
            Path(tmp).unlink(missing_ok=True)


class PosterWidget(Static):
    """Downloads and renders a poster image in the terminal."""

    DEFAULT_CSS = """
    PosterWidget {
        height: auto;
        margin-bottom: 1;
    }
    """

    def __init__(self, url: str, cols: int = 24, rows: int = 12) -> None:
        super().__init__("")
        self._url  = url
        self._cols = cols
        self._rows = rows

    def on_mount(self) -> None:
        self._load()

    @work
    async def _load(self) -> None:
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                r = await client.get(self._url)
                r.raise_for_status()
                png = r.content
        except Exception:
            return

        rendered: str | None = None
        if _PROTOCOL == "kitty":
            rendered = _kitty_render(png, cols=self._cols, rows=self._rows)
        elif _PROTOCOL == "sixel":
            rendered = _sixel_render(png, width=self._cols * 8)
        elif _PROTOCOL == "chafa":
            rendered = _chafa_render(png, cols=self._cols, rows=self._rows)

        if rendered:
            self.update(rendered)
