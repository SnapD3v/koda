from textual.app import ComposeResult
from textual.screen import Screen
from textual.binding import Binding
from textual.widgets import Header, Footer, Button, Static
from textual.containers import Vertical, Horizontal
from textual import on, work

from koda import __version__
from koda.api.kodik import SearchResult, Translation

_TYPE_ICONS = {
    "movie": "🎬", "anime": "🎌", "serial": "📺",
    "anime-serial": "🎌", "cartoon-serial": "🎨",
    "foreign-movie": "🎬", "russian-movie": "🎬",
}

_BANNER = (
    "[bold cyan]🎬  K O D A[/bold cyan]\n"
    "[dim]Console Cinema  •  Kodik API[/dim]\n"
    f"[dim]by SnapD3v  •  github.com/SnapD3v/koda  •  v{__version__}[/dim]"
)


class HomeScreen(Screen):

    BINDINGS = [
        Binding("s", "search",   "Поиск"),
        Binding("l", "library",  "Библиотека"),
        Binding("ctrl+comma", "settings", "Настройки"),
        Binding("u", "updates",  "Обновления"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Vertical(
            Static(_BANNER, id="home-banner"),
            Horizontal(
                Button("🔍 Поиск",       id="btn-search",   variant="primary"),
                Button("📚 Библиотека",  id="btn-library",  variant="default"),
                Button("⚙ Настройки",   id="btn-settings", variant="default"),
                Button("📋 Обновления",  id="btn-updates",  variant="default"),
                id="home-buttons",
            ),
            Static("Недавнее:", id="home-recent-label"),
            Horizontal(id="home-recent"),
            id="home-container",
        )
        yield Footer()

    def on_mount(self) -> None:
        self._load_recent()

    def _load_recent(self) -> None:
        items = self.app.db.get_recent_items(limit=4)
        row = self.query_one("#home-recent")
        if not items:
            self.query_one("#home-recent-label", Static).update(
                "[dim]Недавнее: нет просмотров[/dim]"
            )
            return
        for item in items:
            icon = _TYPE_ICONS.get(item.get("type", ""), "▶")
            prog = self.app.db.get_progress(item["kodik_id"])
            sub = ""
            if prog and item.get("type") not in ("movie", "foreign-movie", "russian-movie"):
                sub = f" С{prog['season']}Е{prog['episode']}"
            btn = Button(f"{icon} {item['title']}{sub}", classes="recent-btn")
            btn._koda_item = item
            row.mount(btn)

    @on(Button.Pressed, "#btn-search")
    def go_search(self) -> None:
        from koda.tui.screens.search import SearchScreen
        self.app.push_screen(SearchScreen())

    @on(Button.Pressed, "#btn-library")
    def go_library(self) -> None:
        from koda.tui.screens.library import LibraryScreen
        self.app.push_screen(LibraryScreen())

    @on(Button.Pressed, "#btn-settings")
    def go_settings(self) -> None:
        from koda.tui.screens.settings import SettingsScreen
        self.app.push_screen(SettingsScreen())

    @on(Button.Pressed, "#btn-updates")
    def go_updates(self) -> None:
        from koda.tui.screens.version import VersionScreen
        self.app.push_screen(VersionScreen())

    @on(Button.Pressed, ".recent-btn")
    def on_recent_pressed(self, event: Button.Pressed) -> None:
        item = getattr(event.button, "_koda_item", None)
        if item:
            self._open_recent(item)

    def action_search(self) -> None:
        from koda.tui.screens.search import SearchScreen
        self.app.push_screen(SearchScreen())

    def action_library(self) -> None:
        from koda.tui.screens.library import LibraryScreen
        self.app.push_screen(LibraryScreen())

    def action_settings(self) -> None:
        from koda.tui.screens.settings import SettingsScreen
        self.app.push_screen(SettingsScreen())

    def action_updates(self) -> None:
        from koda.tui.screens.version import VersionScreen
        self.app.push_screen(VersionScreen())

    @work
    async def _open_recent(self, item: dict) -> None:
        from koda.tui.screens.detail import DetailScreen

        full_result: SearchResult | None = None
        variants: list[SearchResult] = []
        try:
            results, _ = await self.app.kodik.search(item["title"], limit=25)
            groups: dict[tuple, list] = {}
            for r in results:
                key = (r.title.lower(), r.year)
                groups.setdefault(key, []).append(r)
            for group in groups.values():
                if any(r.id == item["kodik_id"] for r in group):
                    variants = group
                    for r in group:
                        if r.id == item["kodik_id"]:
                            full_result = r
                            break
                    break
        except Exception:
            pass

        if full_result is None:
            full_result = SearchResult(
                id            = item["kodik_id"],
                type          = item["type"],
                title         = item["title"],
                title_orig    = "",
                year          = item.get("year") or 0,
                link          = item["kodik_link"],
                quality       = "",
                translation   = Translation(0, "", ""),
                seasons       = {},
                material_data = {},
            )

        self.app.push_screen(DetailScreen(full_result, variants or [full_result]))

    def on_screen_resume(self) -> None:
        self.query_one("#home-recent").remove_children()
        self._load_recent()
