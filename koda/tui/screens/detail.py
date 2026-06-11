import asyncio

from textual.app import ComposeResult
from textual.screen import Screen
from textual.binding import Binding
from textual.widgets import Header, Footer, Label, Button, Static, Select
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual import on, work

from koda.api.kodik import KodikClient, SearchResult
from koda.player.launcher import play
from koda.tui.widgets.poster import PosterWidget, _PROTOCOL


class DetailScreen(Screen):

    BINDINGS = [
        Binding("escape", "app.pop_screen",    "Назад"),
        Binding("p",      "play_default",      "Смотреть"),
        Binding("t",      "cycle_translation", "Озвучка"),
        Binding("s",      "skip_next",         "Пропустить", show=False),
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
        self._next_season:  str = ""
        self._next_episode: str = ""
        self._next_ep_timer = None
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

        episode_widgets: list = []
        if has_episodes:
            episode_widgets = [
                Label("Эпизод:"),
                Select(self._episode_options(self._selected_season), value=self._selected_episode, id="episode-select"),
            ]

        translation_widgets: list = []
        if has_variants:
            opts = [(f"{v.translation.title} [{v.translation.type}]", str(i))
                    for i, v in enumerate(self.variants)]
            translation_widgets = [Label("Озвучка:"), Select(opts, value="0", id="translation-select")]

        poster_url = (self.result.material_data or {}).get("poster_url")
        yield Header()
        yield ScrollableContainer(
            *(
                [PosterWidget(poster_url)]
                if poster_url and _PROTOCOL != "none"
                else []
            ),
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
        s, e = saved_s, saved_e
        self.call_after_refresh(lambda: self._apply_saved_episode(s, e))

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

    @on(Select.Changed, "#episode-select")
    def on_episode_changed(self, event: Select.Changed) -> None:
        self._selected_episode = str(event.value)

    @on(Button.Pressed, "#btn-play")
    async def action_play_default(self) -> None:
        if self._is_playing:
            return
        start_from = await self._resolve_start_from()
        if start_from is None:
            return
        self._stream_and_play(start_from)

    async def _resolve_start_from(self) -> float | None:
        """Returns start timecode, 0.0 for beginning, or None if cancelled."""
        prog = self._progress
        if not prog:
            return 0.0
        season  = int(self._selected_season)  if self._selected_season.isdigit()  else 1
        episode = int(self._selected_episode) if self._selected_episode.isdigit() else 1
        if prog.get("season") == season and prog.get("episode") == episode:
            tc = prog.get("timecode", 0.0)
            if tc > 5:
                from koda.tui.screens.resume_modal import ResumeModal
                return await self.app.push_screen_wait(ResumeModal(tc))
        return 0.0

    @on(Button.Pressed, "#btn-back")
    def on_back(self) -> None:
        self.app.pop_screen()

    @on(Button.Pressed, "#btn-download")
    def on_download(self) -> None:
        self._open_download()

    @work
    async def _open_download(self) -> None:
        from koda.tui.screens.download import DownloadModal
        token      = self.app.config.get("token", "")
        quality    = self.app.config.get("quality", "720")
        active_idx = next((i for i, v in enumerate(self.variants) if v is self._current), 0)
        new_idx    = await self.app.push_screen_wait(
            DownloadModal(self.variants, active_idx, token, quality)
        )
        if isinstance(new_idx, int) and new_idx != active_idx:
            self._current = self.variants[new_idx]
            try:
                self.query_one("#translation-select", Select).value = str(new_idx)
            except Exception:
                pass

    @on(Button.Pressed, "#btn-folder")
    async def on_add_to_folder(self) -> None:
        self._pick_folder()

    # ── Workers ───────────────────────────────────────────────────────────────

    @work
    async def _fetch_material_data(self) -> None:
        """Fetches full material_data from API (used when opening from library)."""
        try:
            results, _ = await self.app.kodik.search(self.result.title, limit=10)
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
    def _stream_and_play(self, start_from: float = 0.0) -> None:
        self._is_playing = True
        link           = self._get_play_link()
        quality        = self.app.config.get("quality", "720")
        token          = self.app.config.get("token", "")
        player         = self.app.config.get("player", "mpv")
        kodik_id       = self.result.id
        season         = int(self._selected_season)  if self._selected_season.isdigit()  else 1
        episode        = int(self._selected_episode) if self._selected_episode.isdigit() else 1
        ep_tag = f" (С{season} Э{episode})" if self._selected_season else ""
        title  = f"{self._current.title}{ep_tag} — {self._current.translation.title}"
        base   = self._current.title_orig or self._current.title
        oscc_title = (
            f"{base} S{season:02d}E{episode:02d}" if self._selected_season else base
        )
        translation_id = next((i for i, v in enumerate(self.variants) if v is self._current), 0)
        media_title    = self._current.title
        media_type     = self.result.type
        media_year     = self.result.year
        media_link     = self.result.link
        poster_url     = (self.result.material_data or {}).get("poster_url")

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
            final_tc = play(url=url, player=player, title=title, start_from=start_from, oscc_title=oscc_title)
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

                next_ep = self._find_next_episode(str(season), str(episode))
                if next_ep:
                    _ns, _ne = next_ep
                    self._progress = self.app.db.get_progress(kodik_id)
                    self.app.call_from_thread(
                        lambda ns=_ns, ne=_ne: self._schedule_next_episode(ns, ne)
                    )
                    return

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

    # ── Auto-advance ──────────────────────────────────────────────────────────

    def _find_next_episode(self, season: str, episode: str) -> tuple[str, str] | None:
        seasons = self._current.seasons or self.result.seasons
        if not seasons:
            return None
        eps = seasons.get(season, {}).get("episodes", {})
        ep_keys = sorted(eps.keys(), key=lambda e: int(e) if e.isdigit() else 0)
        try:
            idx = ep_keys.index(episode)
        except ValueError:
            return None
        if idx + 1 < len(ep_keys):
            return (season, ep_keys[idx + 1])
        season_keys = sorted(seasons.keys(), key=lambda s: int(s) if s.isdigit() else 0)
        try:
            s_idx = season_keys.index(season)
        except ValueError:
            return None
        if s_idx + 1 < len(season_keys):
            next_s = season_keys[s_idx + 1]
            next_eps = seasons.get(next_s, {}).get("episodes", {})
            if next_eps:
                first = sorted(next_eps.keys(), key=lambda e: int(e) if e.isdigit() else 0)[0]
                return (next_s, first)
        return None

    def _schedule_next_episode(self, season: str, episode: str) -> None:
        self._next_season  = season
        self._next_episode = episode
        s = int(season)  if season.isdigit()  else season
        e = int(episode) if episode.isdigit() else episode
        self.query_one("#detail-status", Static).update(
            f"[dim]Следующий: С{s}Э{e} — через 5 сек  •  [bold]S[/bold] — пропустить[/dim]"
        )
        self._next_ep_timer = self.set_timer(5.0, self._auto_next_episode)

    def _auto_next_episode(self) -> None:
        self._next_ep_timer = None
        if not self.is_mounted:
            return
        self._selected_season  = self._next_season
        self._selected_episode = self._next_episode
        s, e = self._selected_season, self._selected_episode
        self.call_after_refresh(lambda: self._apply_saved_episode(s, e))
        self.query_one("#detail-status", Static).update("")
        if not self._is_playing:
            self._stream_and_play(0.0)

    def action_cycle_translation(self) -> None:
        if len(self.variants) <= 1:
            return
        try:
            sel = self.query_one("#translation-select", Select)
            cur = int(sel.value) if sel.value != Select.BLANK else 0
            sel.value = str((cur + 1) % len(self.variants))
        except Exception:
            pass

    def action_skip_next(self) -> None:
        if self._next_ep_timer is not None:
            self._next_ep_timer.stop()
            self._next_ep_timer = None
        self.query_one("#detail-status", Static).update("")

    def on_unmount(self) -> None:
        if self._next_ep_timer is not None:
            self._next_ep_timer.stop()
            self._next_ep_timer = None

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
