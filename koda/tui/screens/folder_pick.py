from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Label, ListView, ListItem, Button, Input
from textual.containers import Vertical
from textual.binding import Binding
from textual import on


class FolderPickScreen(ModalScreen[int | None]):
    """Модальный экран выбора папки. Возвращает folder_id или None."""

    BINDINGS = [Binding("escape", "dismiss(None)", "Отмена")]

    def compose(self) -> ComposeResult:
        folders = self.app.db.get_folders()
        yield Vertical(
            Label("Выбери папку:", id="fp-title"),
            ListView(
                *[ListItem(Label(f['name']), name=str(f['id']))
                  for f in folders],
                id="fp-list",
            ),
            Input(placeholder="Новая папка...", id="fp-new"),
            Button("Создать папку", id="fp-create", variant="primary"),
            id="fp-container",
        )

    @on(ListView.Selected, "#fp-list")
    def on_selected(self, event: ListView.Selected) -> None:
        folder_id = int(event.item.name)
        self.dismiss(folder_id)

    @on(Button.Pressed, "#fp-create")
    def on_create(self) -> None:
        name = self.query_one("#fp-new", Input).value.strip()
        if not name:
            return
        folder_id = self.app.db.create_folder(name)
        self.dismiss(folder_id)