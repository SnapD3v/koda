from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Button, Label
from textual.containers import Horizontal, Vertical
from textual import on


class ResumeModal(ModalScreen[float | None]):
    """Спрашивает продолжить с сохранённой позиции или начать сначала."""

    BINDINGS = [Binding("escape", "cancel", "Отмена", show=False)]

    def __init__(self, timecode: float) -> None:
        super().__init__()
        self._timecode = timecode

    def compose(self) -> ComposeResult:
        mins = int(self._timecode) // 60
        secs = int(self._timecode) % 60
        yield Vertical(
            Label(f"Продолжить просмотр с [bold]{mins}:{secs:02d}[/bold]?", id="rm-label"),
            Horizontal(
                Button(f"▶ Продолжить с {mins}:{secs:02d}", id="rm-resume", variant="primary"),
                Button("↺ С начала",                        id="rm-restart", variant="default"),
                id="rm-btns",
            ),
            id="resume-container",
        )

    @on(Button.Pressed, "#rm-resume")
    def on_resume(self) -> None:
        self.dismiss(self._timecode)

    @on(Button.Pressed, "#rm-restart")
    def on_restart(self) -> None:
        self.dismiss(0.0)

    def action_cancel(self) -> None:
        self.dismiss(None)
