from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, Footer

from koda.config import load_config
from koda.storage.db import Database
from koda.api.kodik import KodikClient


class KodaApp(App):

    CSS_PATH = "app.tcss"

    BINDINGS = [
        Binding("ctrl+q", "quit",    "Выйти"),
        Binding("ctrl+l", "library", "Библиотека"),
    ]

    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.db     = Database()
        self.db.init()

    def on_mount(self) -> None:
        from koda.tui.screens.home import HomeScreen
        self.kodik = KodikClient(self.config.get("token", ""))
        self.push_screen(HomeScreen())

    async def on_unmount(self) -> None:
        await self.kodik._http.aclose()

    def action_library(self) -> None:
        from koda.tui.screens.library import LibraryScreen
        self.push_screen(LibraryScreen())

    def action_settings(self) -> None:
        from koda.tui.screens.settings import SettingsScreen
        self.push_screen(SettingsScreen())

    def action_updates(self) -> None:
        from koda.tui.screens.version import VersionScreen
        self.push_screen(VersionScreen())