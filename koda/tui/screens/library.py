from textual.screen import Screen
from textual.widgets import Header, Footer, Label
from textual.app import ComposeResult


class LibraryScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("Библиотека — в разработке")
        yield Footer()