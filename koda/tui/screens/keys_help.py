from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.binding import Binding
from textual.widgets import Static, Button
from textual.containers import Vertical


_HELP_TEXT = """\
[bold]Глобальные[/bold]
  [cyan]Ctrl+Q[/cyan]      Выйти из приложения
  [cyan]Ctrl+L[/cyan]      Открыть библиотеку
  [cyan]?[/cyan]           Это меню

[bold]Главный экран[/bold]
  [cyan]S[/cyan]           Поиск
  [cyan]L[/cyan]           Библиотека
  [cyan]U[/cyan]           Обновления
  [cyan]Ctrl+,[/cyan]      Настройки

[bold]Поиск[/bold]
  [cyan]Enter / ↑↓[/cyan] Выбор результата
  [cyan]Escape[/cyan]      Назад

[bold]Карточка тайтла[/bold]
  [cyan]P[/cyan]           Смотреть
  [cyan]Escape[/cyan]      Назад

[bold]Библиотека[/bold]
  [cyan]N[/cyan]           Создать папку
  [cyan]D[/cyan]           Удалить выбранное
  [cyan]Escape[/cyan]      Назад / выйти из папки

[bold]Загрузка[/bold]
  [cyan]Escape[/cyan]      Закрыть
"""


class KeysHelpModal(ModalScreen):

    BINDINGS = [
        Binding("escape", "dismiss", "Закрыть"),
        Binding("question_mark", "dismiss", show=False),
    ]

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static("[bold]Горячие клавиши[/bold]", id="kh-title"),
            Static(_HELP_TEXT, id="kh-body"),
            Button("Закрыть  [dim]Esc[/dim]", id="kh-close", variant="default"),
            id="kh-container",
        )

    def on_button_pressed(self) -> None:
        self.dismiss()
