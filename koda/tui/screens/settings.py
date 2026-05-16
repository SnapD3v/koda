import os
import sys
import webbrowser
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Header, Footer, Button, Input, Label, Select, Static
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual import on

from koda.config import save_config
from koda.player.launcher import find_player

_MPV_URL  = "https://mpv.io/installation/"
_OSCC_URL = "https://github.com/0dist/oscc"


def _check_mpv() -> str | None:
    return find_player("mpv")


def _check_oscc() -> bool:
    candidates = [
        Path.home() / ".config" / "mpv" / "scripts" / "oscc.lua",
        Path(os.environ.get("APPDATA", "")) / "mpv" / "scripts" / "oscc.lua",
    ]
    try:
        candidates.append(Path(sys.executable).parent / "mpv" / "scripts" / "oscc.lua")
    except Exception:
        pass
    return any(p.exists() for p in candidates)


class SettingsScreen(Screen):

    BINDINGS = [Binding("escape", "back", "Назад")]

    def compose(self) -> ComposeResult:
        cfg = self.app.config
        player_val = cfg.get("player", "mpv")
        is_custom  = player_val not in ("mpv", "vlc")
        custom_val = player_val if is_custom else ""

        yield Header()
        yield ScrollableContainer(
            Label("Токен Kodik API:", classes="s-label"),
            Input(value=cfg.get("token", ""), placeholder="Введи токен...", id="s-token"),

            Label("Плеер:", classes="s-label"),
            Select(
                [("mpv (рекомендован)", "mpv"), ("VLC", "vlc"), ("Другой...", "custom")],
                value="custom" if is_custom else player_val,
                id="s-player",
            ),
            Input(
                value=custom_val,
                placeholder="Путь к исполняемому файлу плеера...",
                id="s-player-custom",
                classes="hidden" if not is_custom else "",
            ),
            Static("", id="s-player-status"),
            Horizontal(
                Button("Скачать mpv",     id="s-dl-mpv",  variant="warning"),
                Button("Установить oscc", id="s-dl-oscc", variant="warning"),
                id="s-player-links",
            ),

            Label("Качество видео:", classes="s-label"),
            Select(
                [("360p", "360"), ("480p", "480"), ("720p", "720"), ("1080p", "1080")],
                value=cfg.get("quality", "720"),
                id="s-quality",
            ),

            Label("Папка для загрузок:", classes="s-label"),
            Input(
                value=cfg.get("downloads_dir", str(Path.home() / "Videos" / "Koda")),
                placeholder=str(Path.home() / "Videos" / "Koda"),
                id="s-dldir",
            ),

            id="s-form",
        )
        yield Horizontal(
            Button("💾 Сохранить", id="s-save", variant="success"),
            Button("← Назад",     id="s-back", variant="default"),
            id="s-btn-row",
        )
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_player_status()

    def _refresh_player_status(self) -> None:
        mpv_path = _check_mpv()
        oscc_ok  = _check_oscc()
        mpv_text = (
            f"[green]✓ mpv: {mpv_path}[/green]"
            if mpv_path else "[red]✗ mpv не найден[/red]"
        )
        oscc_text = (
            "[green]✓ oscc установлен[/green]"
            if oscc_ok else "[yellow]✗ oscc не найден[/yellow]"
        )
        self.query_one("#s-player-status", Static).update(
            f"{mpv_text}   {oscc_text}"
        )

    @on(Select.Changed, "#s-player")
    def on_player_changed(self, event: Select.Changed) -> None:
        custom_input = self.query_one("#s-player-custom", Input)
        if event.value == "custom":
            custom_input.remove_class("hidden")
        else:
            custom_input.add_class("hidden")

    @on(Button.Pressed, "#s-dl-mpv")
    def on_dl_mpv(self) -> None:
        webbrowser.open(_MPV_URL)

    @on(Button.Pressed, "#s-dl-oscc")
    def on_dl_oscc(self) -> None:
        webbrowser.open(_OSCC_URL)

    @on(Button.Pressed, "#s-save")
    def on_save(self) -> None:
        player_select = self.query_one("#s-player", Select).value
        if player_select == "custom":
            player_val = self.query_one("#s-player-custom", Input).value.strip() or "mpv"
        else:
            player_val = str(player_select)

        new_cfg = dict(self.app.config)
        new_cfg["token"]         = self.query_one("#s-token",   Input).value.strip()
        new_cfg["player"]        = player_val
        new_cfg["quality"]       = str(self.query_one("#s-quality",  Select).value)
        new_cfg["downloads_dir"] = self.query_one("#s-dldir",   Input).value.strip() or str(
            Path.home() / "Videos" / "Koda"
        )

        save_config(new_cfg)
        self.app.config = new_cfg
        self.app.kodik  = type(self.app.kodik)(new_cfg.get("token", ""))
        self.app.notify("Настройки сохранены")

    @on(Button.Pressed, "#s-back")
    def action_back(self) -> None:
        self.app.pop_screen()
