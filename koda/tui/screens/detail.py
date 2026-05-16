import asyncio

from textual.app import ComposeResult
from textual.screen import Screen
from textual.binding import Binding
from textual.widgets import Header, Footer, Label, Button, Static, Select
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual import on, work

from koda.api.kodik import KodikClient, SearchResult
from koda.player.launcher import play


class DetailScreen(Screen):

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Назад"),
        Binding("p",      "play_default",   "Смотреть"),
    ]

    def __init__(self, result: SearchResult, variants: list[SearchResult] | None = None) -> None:
        super().__init__()
        self.result   = result
        self.variants = variants or [result]
        self._current = self.result
        self._progress:   dict | None = None
        self._is_playing: bool = False

        self._selected_season:  str = ""
        self._selected_episode: str = ""
        if result.seasons:
            first = next(iter(sorted(result.seasons, key=lambda s: int(s) if s.isdigit() else 0)))
            self._selected_season = first
            eps = result.seasons[first].get("episodes", {})
            if eps:
                self._selected_episode = next(iter(sorted(eps, key=lambda e: int(e) if e.isdigit() else 0)))

    # ── Compose ──────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        has_variants = len(self.variants) > 1
        has_episodes = bool(self.result.seasons)

        translation_widgets: list = []
        if has_variants:
            opts = [(f"{v.translation.title} [{v.translation.type}]", str(i))
                    for i, v in enumerate(self.variants)]
            translation_widgets = [Label("Озвучка:"), Select(opts, value="0", id="translation-select")]

        episode_widgets: list = []
        if has_episodes:
            episode_widgets = [
                Label("Сезон:"),
                Select(self._season_options(), value=self._selected_season, id="season-select"),
                Label("Эпизод:"),
                Select(self._episode_options(self._selected_season), value=self._selected_episode, id="episode-select"),
            ]

        yield Header()
        yield ScrollableContainer(
            Static(self._build_info(), id="detail-info"),
            id="detail-scroll",
        )
        yield Vertical(
            *translation_widgets,
            *episode_widgets,
            Horizontal(
                Button("▶ Смотреть", id="btn-play",     variant="success"),
                Button("⬇ Скачать",  id="btn-download", variant="warning"),
                Button("♥ В папку",  id="btn-folder",   variant="primary"),
                Button("← Назад",    id="btn-back",     variant="default"),
                id="detail-buttons",
            ),
            Static("", id="detail-status"),
            id="detail-controls",
        )
        yield Footer()

    def on_mount(self) -> None:
        self._progress = self.app.db.get_progress(self.result.id)
        if self._progress:
            self._restore_translation()
        if self._progress and self.result.seasons:
            self._restore_progress_selection()
        if self._progress:
            self.query_one("#detail-info", Static).update(self._build_info())
        if not self.result.material_data:
            self._fetch_material_data()

    def _restore_translation(self) -> None:
        saved_idx = self._progress.get("translation_id", 0)
        if saved_idx >= len(self.variants):
            return
        self._current = self.variants[saved_idx]
        try:
            self.query_one("#translation-select", Select).value = str(saved_idx)
        except Exception:
            pass

    def _restore_progress_selection(self) -> None:
        saved_s = str(self._progress.get("season",  1))
        saved_e = str(self._progress.get("episode", 1))
        if saved_s not in self.result.seasons:
            return
        eps = self.result.seasons[saved_s].get("episodes", {})
        if saved_e not in eps:
            return
        self._selected_season  = saved_s
        self._selected_episode = saved_e
        try:
            self.query_one("#season-select", Select).value = saved_s
            s, e = saved_s, saved_e
            self.call_after_refresh(lambda: self._apply_saved_episode(s, e))
        except Exception:
            pass

    def _apply_saved_episode(self, season: str, episode: str) -> None:
        try:
            ep_select = self.query_one("#episode-select", Select)
            ep_select.set_options(self._episode_options(season))
            ep_select.value = episode
            self._selected_season  = season
            self._selected_episode = episode
        except Exception:
            pass

    # ── Season/episode helpers ────────────────────────────────────────────────

    def _season_options(self) -> list[tuple[str, str]]:
        keys = sorted(self.result.seasons, key=lambda s: int(s) if s.isdigit() else 0)
        return [(f"Сезон {s}", s) for s in keys]

    def _episode_options(self, season: str) -> list[tuple[str, str]]:
        eps = self.result.seasons.get(season, {}).get("episodes", {})
        keys = sorted(eps, key=lambda e: int(e) if e.isdigit() else 0)
        return [(f"Эпизод {e}", e) for e in keys]

    # ── Info text ─────────────────────────────────────────────────────────────

    def _build_info(self, result: SearchResult | None = None) -> str:
        r = result or self.result
        lines = [f"[bold]{r.title}[/bold]"]
        if r.title_orig and r.title_orig != r.title:
            lines.append(f"[dim]{r.title_orig}[/dim]")
        lines += [
            f"\nГод: {r.year}" if r.year else "",
            f"Тип: {r.type}",
            f"Качество: {r.quality}" if r.quality else "",
        ]
        if r.material_data:
            for key in ("rating_kinopoisk", "rating_imdb"):
                val = r.material_data.get(key)
                if val:
                    label = "КиноПоиск" if "kinopoisk" in key else "IMDb"
                    lines.append(f"{label}: {val}")
            genres = r.material_data.get("genres") or r.material_data.get("anime_genres")
            if genres:
                lines.append("\nЖанры: " + ", ".join(genres[:5]))
            desc = r.material_data.get("description", "")
            if desc:
                lines += ["\nОписание: ", desc]

        if self._progress and (self._progress.get("timecode") or 0) > 5:
            tc   = int(self._progress["timecode"])
            mins = tc // 60
            secs = tc % 60
            s    = self._progress.get("season",  1)
            e    = self._progress.get("episode", 1)
            if self.result.seasons:
                lines += ["", f"[green]▶ Продолжить: С{s}Е{e} с {mins}:{secs:02d}[/green]"]
            else:
                lines += ["", f"[green]▶ Продолжить с {mins}:{secs:02d}[/green]"]

        return "\n".join(l for l in lines if l)

    # ── Event handlers ────────────────────────────────────────────────────────

    @on(Select.Changed, "#translation-select")
    def on_translation_changed(self, event: Select.Changed) -> None:
        self._current = self.variants[int(event.value)]
        self.query_one("#detail-info", Static).update(self._build_info(self._current))

    @on(Select.Changed, "#season-select")
    def on_season_changed(self, event: Select.Changed) -> None:
        self._selected_season = str(event.value)
        ep_opts = self._episode_options(self._selected_season)
        self.query_one("#episode-select", Select).set_options(ep_opts)
        self._selected_episode = ep_opts[0][1] if ep_opts else ""

    @on(Select.Changed, "#episode-select")
    def on_episode_changed(self, event: Select.Changed) -> None:
        self._selected_episode = str(event.value)

    @on(Button.Pressed, "#btn-play")
    def action_play_default(self) -> None:
        if not self._is_playing:
            self._stream_and_play()

    @on(Button.Pressed, "#btn-back")
    def on_back(self) -> None:
        self.app.pop_screen()

    @on(Button.Pressed, "#btn-download")
    def on_download(self) -> None:
        self._open_download()

    @work
    async def _open_download(self) -> None:
        from koda.tui.screens.download import DownloadModal
        token   = self.app.config.get("token", "")
        quality = self.app.config.get("quality", "720")
        src = self._current if self._current.seasons else self.result
        await self.app.push_screen_wait(DownloadModal(src, token, quality))

    @on(Button.Pressed, "#btn-folder")
    async def on_add_to_folder(self) -> None:
        self._pick_folder()

    # ── Workers ───────────────────────────────────────────────────────────────

    @work
    async def _fetch_material_data(self) -> None:
        """Fetches full material_data from API (used when opening from library)."""
        try:
            results = await self.app.kodik.search(self.result.title, limit=10)
            for r in results:
                if r.id == self.result.id or (
                    r.title.lower() == self.result.title.lower() and r.year == self.result.year
                ):
                    self.result.material_data = r.material_data
                    self.result.quality       = r.quality or self.result.quality
                    self.result.seasons       = r.seasons or self.result.seasons
                    self.query_one("#detail-info", Static).update(self._build_info())
                    # Seasons may have been empty on mount — restore selection now
                    if self._progress and self.result.seasons:
                        self._restore_progress_selection()
                    return
        except Exception:
            pass

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
        folder_name = next((f["name"] for f in folders if f["id"] == folder_id), "папку")
        self.query_one("#detail-status", Static).update(
            f'[green]Добавлено в "{folder_name}"[/green]'
        )

    @work(thread=True)
    def _stream_and_play(self) -> None:
        self._is_playing = True
        link           = self._get_play_link()
        quality        = self.app.config.get("quality", "720")
        token          = self.app.config.get("token", "")
        player         = self.app.config.get("player", "mpv")
        title          = f"{self._current.title} — {self._current.translation.title}"
        kodik_id       = self.result.id
        season         = int(self._selected_season)  if self._selected_season.isdigit()  else 1
        episode        = int(self._selected_episode) if self._selected_episode.isdigit() else 1
        translation_id = next((i for i, v in enumerate(self.variants) if v is self._current), 0)
        media_title    = self._current.title
        media_type     = self.result.type
        media_year     = self.result.year
        media_link     = self.result.link
        poster_url     = (self.result.material_data or {}).get("poster_url")

        start_from = 0.0
        prog = self._progress
        if prog and prog.get("season") == season and prog.get("episode") == episode:
            tc = prog.get("timecode", 0.0)
            if tc > 5:
                start_from = tc

        self.app.call_from_thread(
            lambda: self.query_one("#detail-status", Static).update("Получаем ссылку...")
        )
        try:
            url = asyncio.run(self._resolve_url(token, link, quality))
            if not url:
                self.app.call_from_thread(
                    lambda: self.query_one("#detail-status", Static).update(
                        "[red]Не удалось получить ссылку[/red]"
                    )
                )
                return

            self.app.call_from_thread(
                lambda: self.query_one("#detail-status", Static).update("Запуск плеера...")
            )
            final_tc = play(url=url, player=player, title=title, start_from=start_from)
            self.app.db.save_progress(kodik_id, season=season, episode=episode, timecode=final_tc, translation_id=translation_id)

            if final_tc > 5:
                wl = self.app.db.get_folder_by_name("Смотреть дальше")
                if wl:
                    self.app.db.add_to_folder(wl["id"], {
                        "kodik_id":   kodik_id,
                        "title":      media_title,
                        "type":       media_type,
                        "year":       media_year,
                        "kodik_link": media_link,
                        "poster_url": poster_url,
                    })

            self._progress = self.app.db.get_progress(kodik_id)
            self.app.call_from_thread(
                lambda: self.query_one("#detail-status", Static).update("")
            )
        except Exception as e:
            err = str(e)
            self.app.call_from_thread(
                lambda: self.query_one("#detail-status", Static).update(f"[red]{err}[/red]")
            )
        finally:
            self._is_playing = False

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_play_link(self) -> str:
        seasons = self._current.seasons or self.result.seasons
        if seasons:
            if self._selected_season and self._selected_episode:
                eps     = seasons.get(self._selected_season, {}).get("episodes", {})
                ep_link = eps.get(self._selected_episode)
                if isinstance(ep_link, str) and ep_link:
                    return ep_link
                if isinstance(ep_link, dict) and ep_link.get("link"):
                    return ep_link["link"]
            for season_data in seasons.values():
                for ep_link in season_data.get("episodes", {}).values():
                    if isinstance(ep_link, str) and ep_link:
                        return ep_link
                    if isinstance(ep_link, dict) and ep_link.get("link"):
                        return ep_link["link"]
        return self._current.link

    @staticmethod
    async def _resolve_url(token: str, link: str, quality: str) -> str | None:
        async with KodikClient(token) as client:
            return await client.get_stream_url(link, preferred_quality=quality)
