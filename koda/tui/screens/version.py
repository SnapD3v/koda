import re
import webbrowser

import httpx

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Header, Footer, Button, Markdown, Static, ProgressBar
from textual.containers import Horizontal, ScrollableContainer
from textual import on, work

from koda import __version__
from koda.updater import (
    GITHUB_REPO,
    download_update,
    apply_update,
    is_frozen,
)

_API_URL  = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
_GH_URL   = f"https://github.com/{GITHUB_REPO}"

_STRIP_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def _clean_body(text: str) -> str:
    text = _STRIP_RE.sub("", text)
    return text.strip()


class VersionScreen(Screen):

    BINDINGS = [Binding("escape", "app.pop_screen", "Назад")]

    def __init__(self) -> None:
        super().__init__()
        self._latest_url: str  = _GH_URL
        self._update_tag: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield ScrollableContainer(
            Static(self._local_info(), id="ver-local"),
            Static("[dim]Проверка обновлений...[/dim]", id="ver-header"),
            Markdown("", id="ver-body"),
            ProgressBar(total=100, id="ver-progress", show_eta=False),
            Static("", id="ver-dl-status"),
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
        self.query_one("#ver-progress", ProgressBar).display = False
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

            if tag.lstrip("v") == __version__:
                status = "[green]✓ актуально[/green]"
            else:
                status = f"[yellow]⚠ доступно обновление {tag}[/yellow]"
                self._update_tag = tag
                self.query_one("#ver-dl", Button).label = "⬇ Установить обновление"

            header.update(f"Версия: [bold]{tag}[/bold]   {status}\nДата:   {pub}\n")
            await body_widget.update(body if body else "*нет описания*")
        except Exception as e:
            header.update(f"[red]Ошибка при проверке обновлений: {e}[/red]")

    @on(Button.Pressed, "#ver-gh")
    def on_open_github(self) -> None:
        webbrowser.open(_GH_URL)

    @on(Button.Pressed, "#ver-dl")
    def on_download(self) -> None:
        if self._update_tag:
            self._do_download_update(self._update_tag)
        else:
            webbrowser.open(self._latest_url)

    @work
    async def _do_download_update(self, tag: str) -> None:
        btn      = self.query_one("#ver-dl", Button)
        progress = self.query_one("#ver-progress", ProgressBar)
        status   = self.query_one("#ver-dl-status", Static)

        btn.disabled = True
        progress.display = True
        status.update("[dim]Скачивание...[/dim]")

        def _on_progress(done: int, total: int) -> None:
            if total > 0:
                pct = int(done * 100 / total)
                progress.update(progress=pct)

        try:
            tmp = await download_update(tag, on_progress=_on_progress)
        except Exception as e:
            progress.display = False
            status.update(f"[red]Ошибка при скачивании: {e}[/red]")
            btn.disabled = False
            return

        progress.update(progress=100)

        if is_frozen():
            status.update("[yellow]Применяем обновление — приложение перезапустится...[/yellow]")
            apply_update(tmp)
        else:
            status.update(f"[green]Файл сохранён:[/green] {tmp}")
            btn.disabled = False

    @on(Button.Pressed, "#ver-back")
    def on_back(self) -> None:
        self.app.pop_screen()
