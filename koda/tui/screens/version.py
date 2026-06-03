import webbrowser

import httpx

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Header, Footer, Button, Static
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual import on, work

from koda import __version__

GITHUB_REPO = "SnapD3v/koda"
_API_URL    = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
_GH_URL     = f"https://github.com/{GITHUB_REPO}"


class VersionScreen(Screen):

    BINDINGS = [Binding("escape", "app.pop_screen", "Назад")]

    def __init__(self) -> None:
        super().__init__()
        self._latest_url: str = _GH_URL

    def compose(self) -> ComposeResult:
        yield Header()
        yield ScrollableContainer(
            Static(self._local_info(), id="ver-local"),
            Static("[dim]Проверка обновлений...[/dim]", id="ver-remote"),
            Horizontal(
                Button("Открыть GitHub",         id="ver-gh"),
                Button("Скачать последний билд", id="ver-dl"),
                Button("← Назад",                id="ver-back", variant="default"),
                id="ver-btns",
            ),
            id="ver-container",
        )
        yield Footer()

    def on_mount(self) -> None:
        self._fetch_latest()

    def _local_info(self) -> str:
        return (
            f"Текущая версия: [bold]v{__version__}[/bold]\n"
            f"Автор: SnapD3v\n"
            f"GitHub: {_GH_URL}\n"
            "Поддержать: скоро...\n"
        )

    @work
    async def _fetch_latest(self) -> None:
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                r = await client.get(
                    _API_URL,
                    headers={"Accept": "application/vnd.github+json"},
                    follow_redirects=True,
                )
            if r.status_code == 404:
                self._set_remote("[dim]Релизы ещё не созданы.[/dim]")
                return
            if r.status_code != 200:
                self._set_remote(
                    f"[yellow]GitHub API вернул {r.status_code}[/yellow]"
                )
                return

            data        = r.json()
            tag         = data.get("tag_name", "?")
            body        = (data.get("body") or "").strip()[:600]
            pub         = (data.get("published_at") or "")[:10]
            html        = data.get("html_url", _GH_URL)
            self._latest_url = html

            status = (
                "[green]✓ актуально[/green]"
                if tag.lstrip("v") == __version__
                else f"[yellow]⚠ доступно обновление {tag}[/yellow]"
            )

            lines = [
                "─── Последний релиз ───",
                f"Версия: [bold]{tag}[/bold]   {status}",
                f"Дата:   {pub}",
                "",
                body if body else "(нет описания)",
            ]
            self._set_remote("\n".join(lines))
        except Exception as e:
            self._set_remote(f"[red]Ошибка при проверке обновлений: {e}[/red]")

    def _set_remote(self, text: str) -> None:
        try:
            self.query_one("#ver-remote", Static).update(text)
        except Exception:
            pass

    @on(Button.Pressed, "#ver-gh")
    def on_open_github(self) -> None:
        webbrowser.open(_GH_URL)

    @on(Button.Pressed, "#ver-dl")
    def on_download_latest(self) -> None:
        webbrowser.open(self._latest_url)

    @on(Button.Pressed, "#ver-back")
    def on_back(self) -> None:
        self.app.pop_screen()
