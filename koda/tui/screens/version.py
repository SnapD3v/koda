import re
import webbrowser

import httpx

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Header, Footer, Button, Markdown, Static
from textual.containers import Horizontal, ScrollableContainer
from textual import on, work

from koda import __version__

GITHUB_REPO = "SnapD3v/koda"
_API_URL    = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
_GH_URL     = f"https://github.com/{GITHUB_REPO}"

_STRIP_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def _clean_body(text: str) -> str:
    text = _STRIP_RE.sub("", text)
    return text.strip()


class VersionScreen(Screen):

    BINDINGS = [Binding("escape", "app.pop_screen", "Назад")]

    def __init__(self) -> None:
        super().__init__()
        self._latest_url: str = _GH_URL

    def compose(self) -> ComposeResult:
        yield Header()
        yield ScrollableContainer(
            Static(self._local_info(), id="ver-local"),
            Static("[dim]Проверка обновлений...[/dim]", id="ver-header"),
            Markdown("", id="ver-body"),
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
        header = self.query_one("#ver-header", Static)
        body_widget = self.query_one("#ver-body", Markdown)
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                r = await client.get(
                    _API_URL,
                    headers={"Accept": "application/vnd.github+json"},
                    follow_redirects=True,
                )
            if r.status_code == 404:
                header.update("[dim]Релизы ещё не созданы.[/dim]")
                return
            if r.status_code != 200:
                header.update(f"[yellow]GitHub API вернул {r.status_code}[/yellow]")
                return

            data = r.json()
            tag  = data.get("tag_name", "?")
            body = _clean_body(data.get("body") or "")
            pub  = (data.get("published_at") or "")[:10]
            self._latest_url = data.get("html_url", _GH_URL)

            status = (
                "[green]✓ актуально[/green]"
                if tag.lstrip("v") == __version__
                else f"[yellow]⚠ доступно обновление {tag}[/yellow]"
            )
            header.update(f"Версия: [bold]{tag}[/bold]   {status}\nДата:   {pub}\n")
            await body_widget.update(body if body else "*нет описания*")
        except Exception as e:
            header.update(f"[red]Ошибка при проверке обновлений: {e}[/red]")

    @on(Button.Pressed, "#ver-gh")
    def on_open_github(self) -> None:
        webbrowser.open(_GH_URL)

    @on(Button.Pressed, "#ver-dl")
    def on_download_latest(self) -> None:
        webbrowser.open(self._latest_url)

    @on(Button.Pressed, "#ver-back")
    def on_back(self) -> None:
        self.app.pop_screen()
