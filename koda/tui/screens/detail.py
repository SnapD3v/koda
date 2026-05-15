from textual.app import ComposeResult
from textual.screen import Screen
from textual.binding import Binding
from textual.widgets import Header, Footer, Label, Button, Static, ListView, ListItem, Select
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual import on, work

from koda.api.kodik import SearchResult
from koda.player.launcher import play


class DetailScreen(Screen):
    """Экран детальной информации о фильме/сериале."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Назад"),
        Binding("p",      "play_default",   "Смотреть"),
    ]

    def __init__(self, result: SearchResult, variants: list[SearchResult] | None = None) -> None:
        super().__init__()
        self.result = result
        self.variants = variants or [result]
        self._current = self.result

    def compose(self) -> ComposeResult:
        options = [
                    (f"{v.translation.title} [{v.translation.type}]", str(i))
                    for i, v in enumerate(self.variants)
                ]

        yield Header()
        yield ScrollableContainer(
            Vertical(
                Static(self._build_info(), id="detail-info"),
                *(
                    [Label("Озвучка:"),
                     Select(options, value="0", id="translation-select")]
                    if len(self.variants) > 1 else []
                ),
                Horizontal(
                    Button("▶ Смотреть",     id="btn-play",    variant="success"),
                    Button("♥ В папку",      id="btn-folder",  variant="primary"),
                    Button("← Назад",        id="btn-back",    variant="default"),
                    id="detail-buttons",
                ),
                Static("", id="detail-status"),
                id="detail-content",
            )
        )
        yield Footer()

    @on(Select.Changed, "#translation-select")
    def on_translation_changed(self, event: Select.Changed) -> None:
        idx = int(event.value)
        self._current = self.variants[idx]
        self.query_one("#detail-info", Static).update(
            self._build_info(self._current)
        )

    def _build_info(self, result: SearchResult | None = None) -> str:
        r = result or self.result
        lines = [
            f"[bold]{r.title}[/bold]",
        ]
        if r.title_orig and r.title_orig != r.title:
            lines.append(f"[dim]{r.title_orig}[/dim]")
        lines += [
            f"Год: {r.year}" if r.year else "",
            f"Тип: {r.type}",
            f"Качество: {r.quality}" if r.quality else "",
        ]
        if r.material_data:
            desc = r.material_data.get("description", "")
            if desc:
                lines += ["", desc[:300] + ("..." if len(desc) > 300 else "")]
        return "\n".join(l for l in lines if l)

    def _build_episodes(self) -> str:
        """Формирует текст со списком сезонов и эпизодов."""
        lines = ["\n[bold]Эпизоды:[/bold]"]
        for season_num, season_data in sorted(self.result.seasons.items()):
            episodes = season_data.get("episodes", {})
            lines.append(f"\n  Сезон {season_num} ({len(episodes)} эп.)")
        return "\n".join(lines)

    @on(Button.Pressed, "#btn-play")
    def action_play_default(self) -> None:
        self._stream_and_play()

    @on(Button.Pressed, "#btn-back")
    def on_back(self) -> None:
        self.app.pop_screen()

    @on(Button.Pressed, "#btn-folder")
    async def on_add_to_folder(self) -> None:
        self._pick_folder()

    @work
    async def _pick_folder(self) -> None:
        from koda.tui.screens.folder_pick import FolderPickScreen

        folder_id = await self.app.push_screen_wait(FolderPickScreen())
        if folder_id is None:
            return

        self.app.db.add_to_folder(folder_id, {
            "kodik_id":   self.result.id,
            "title":      self.result.title,
            "type":       self.result.type,
            "year":       self.result.year,
            "kodik_link": self.result.link,
            "poster_url": (self.result.material_data or {}).get("poster_url"),
        })
        folders = self.app.db.get_folders()
        folder_name = next(
            (f["name"] for f in folders if f["id"] == folder_id), "папку"
        )
        self.query_one("#detail-status", Static).update(
            f'[green]Добавлено в "{folder_name}"[/green]'
        )

    @work
    async def _stream_and_play(self) -> None:
        self.query_one("#detail-status", Static).update("Получаем ссылку...")
        try:
            url = await self.app.kodik.get_stream_url(
                self._current.link,
                preferred_quality=self.app.config.get("quality", "720"),
            )
            if not url:
                self.query_one("#detail-status", Static).update(
                    "[red]Не удалось получить ссылку[/red]"
                )
                return

            self.app.db.save_progress(self.result.id)

            self.query_one("#detail-status", Static).update("Запуск плеера...")
            play(
                url=url,
                player=self.app.config.get("player", "mpv"),
                title=f"{self._current.title} — {self._current.translation.title}",
            )
            self.query_one("#detail-status", Static).update("")
        except Exception as e:
            self.query_one("#detail-status", Static).update(f"[red]{e}[/red]")