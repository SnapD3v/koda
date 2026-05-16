import asyncio
import re
import shutil
import subprocess
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Footer, Header, Label, ListItem, ListView, Select, SelectionList, Static
from textual import on, work

from koda.api.kodik import KodikClient, SearchResult

_DEFAULT_DOWNLOAD_DIR = Path.home() / "Downloads" / "Koda"


def _get_download_dir(app) -> Path:
    return Path(app.config.get("downloads_dir", str(_DEFAULT_DOWNLOAD_DIR)))


def find_ffmpeg() -> str | None:
    if path := shutil.which("ffmpeg"):
        return path
    for p in [
        Path(r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"),
        Path.home() / "scoop" / "apps" / "ffmpeg" / "current" / "bin" / "ffmpeg.exe",
        Path.home() / "scoop" / "shims" / "ffmpeg.exe",
    ]:
        if p.exists():
            return str(p)
    return None


def _safe(s: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", s).strip()


# ── Local file browser ───────────────────────────────────────────────────────

class LocalFileItem(ListItem):
    def __init__(self, label: str, path: Path) -> None:
        super().__init__()
        self.file_path   = path
        self._label_text = label

    def compose(self) -> ComposeResult:
        yield Label(self._label_text)


class LocalFilesScreen(Screen):
    """Shows downloaded episodes for an item in the 'Скачано' folder."""

    BINDINGS = [Binding("escape", "app.pop_screen", "Назад")]

    def __init__(self, item: dict) -> None:
        super().__init__()
        self.item = item

    def compose(self) -> ComposeResult:
        files = self._scan_files()
        yield Header()
        yield Vertical(
            Static(
                f"[bold]{self.item['title']}[/bold]  •  Локальные файлы",
                id="lf-title",
            ),
            ListView(
                *(LocalFileItem(f["label"], f["path"]) for f in files),
                id="lf-list",
            ) if files else Static(
                "[dim]Файлы не найдены — возможно, удалены из папки Downloads.[/dim]",
                id="lf-empty",
            ),
            Static("", id="lf-status"),
            id="lf-container",
        )
        yield Footer()

    def _scan_files(self) -> list[dict]:
        title = self.item["title"]
        files: list[dict] = []

        dl_dir = _get_download_dir(self.app)
        movie = dl_dir / f"{_safe(title)}.mp4"
        if movie.exists():
            mb = movie.stat().st_size / 1_048_576
            files.append({"label": f"▶  {title}  ({mb:.0f} МБ)", "path": movie})

        base = dl_dir / _safe(title)
        if base.is_dir():
            for season_dir in sorted(base.iterdir()):
                if not season_dir.is_dir():
                    continue
                m = re.match(r"Season (\d+)", season_dir.name)
                s = int(m.group(1)) if m else 0
                for ep_file in sorted(season_dir.glob("*.mp4")):
                    em = re.match(r"S(\d+)E(\d+)", ep_file.stem)
                    e  = int(em.group(2)) if em else 0
                    mb = ep_file.stat().st_size / 1_048_576
                    files.append({
                        "label": f"▶  С{s:02d}Е{e:02d}   ({mb:.0f} МБ)",
                        "path": ep_file,
                    })
        return files

    @on(ListView.Selected, "#lf-list")
    def on_file_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, LocalFileItem):
            self._play_file(event.item.file_path)

    @work(thread=True)
    def _play_file(self, path: Path) -> None:
        from koda.player.launcher import play
        player = self.app.config.get("player", "mpv")
        self.app.call_from_thread(
            lambda: self.query_one("#lf-status", Static).update("Запуск плеера...")
        )
        play(url=str(path), player=player, title=self.item["title"])
        self.app.call_from_thread(
            lambda: self.query_one("#lf-status", Static).update("")
        )


# ── Download modal ───────────────────────────────────────────────────────────

class DownloadModal(ModalScreen):

    BINDINGS = [Binding("escape", "close", "Закрыть")]

    def __init__(self, result: SearchResult, token: str, quality: str) -> None:
        super().__init__()
        self.result       = result
        self.token        = token
        self.quality      = quality
        self._downloading = False

    # ── Compose ──────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        has_seasons = bool(self.result.seasons)
        body: list = [Label(f"Скачать: {self.result.title}", id="dl-title")]

        if has_seasons:
            seasons     = sorted(self.result.seasons, key=lambda s: int(s) if s.isdigit() else 0)
            first       = seasons[0]
            season_opts = [(f"Сезон {s}", s) for s in seasons]
            body += [
                Label("Сезон:", classes="dl-label"),
                Select(season_opts, value=first, id="dl-season"),
                SelectionList(*self._ep_selections(first), id="dl-episodes"),
                Horizontal(
                    Button("Все",   id="dl-all",  variant="default"),
                    Button("Снять", id="dl-none", variant="default"),
                    id="dl-sel-row",
                ),
            ]

        body += [
            Static("", id="dl-status"),
            Horizontal(
                Button("⬇ Скачать", id="dl-start", variant="success"),
                Button("✕ Закрыть", id="dl-close", variant="default"),
                id="dl-btn-row",
            ),
        ]

        yield Vertical(*body, id="dl-container")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _ep_selections(self, season: str) -> list[tuple[str, str]]:
        eps  = self.result.seasons.get(season, {}).get("episodes", {})
        keys = sorted(eps, key=lambda e: int(e) if e.isdigit() else 0)
        return [(f"Эпизод {e}", e) for e in keys]

    # ── Event handlers ────────────────────────────────────────────────────────

    @on(Select.Changed, "#dl-season")
    def on_season_changed(self, event: Select.Changed) -> None:
        if self._downloading:
            return
        ep_list = self.query_one("#dl-episodes", SelectionList)
        ep_list.clear_options()
        for prompt, value in self._ep_selections(str(event.value)):
            ep_list.add_option((prompt, value))

    @on(Button.Pressed, "#dl-all")
    def on_select_all(self) -> None:
        self.query_one("#dl-episodes", SelectionList).select_all()

    @on(Button.Pressed, "#dl-none")
    def on_deselect_all(self) -> None:
        self.query_one("#dl-episodes", SelectionList).deselect_all()

    @on(Button.Pressed, "#dl-close")
    def action_close(self) -> None:
        if not self._downloading:
            self.dismiss(None)

    @on(Button.Pressed, "#dl-start")
    def on_start(self) -> None:
        if self._downloading:
            return

        season       = ""
        selected_eps: list[str] = []

        if self.result.seasons:
            try:
                season       = str(self.query_one("#dl-season", Select).value)
                selected_eps = [str(v) for v in self.query_one("#dl-episodes", SelectionList).selected]
            except Exception:
                pass
            if not selected_eps:
                self.query_one("#dl-status", Static).update(
                    "[yellow]Выбери хотя бы один эпизод[/yellow]"
                )
                return

        self._run_download(season, selected_eps)

    # ── Worker ────────────────────────────────────────────────────────────────

    @work(thread=True)
    def _run_download(self, season: str, episodes: list[str]) -> None:
        def status(msg: str) -> None:
            self.app.call_from_thread(
                lambda m=msg: self.query_one("#dl-status", Static).update(m)
            )

        ffmpeg = find_ffmpeg()
        if not ffmpeg:
            status("[red]ffmpeg не найден. Установи ffmpeg для скачивания.[/red]")
            return

        self._downloading = True
        try:
            if season and episodes:
                self._download_serial(ffmpeg, season, episodes, status)
            else:
                self._download_movie(ffmpeg, status)
        finally:
            self._downloading = False

    def _download_serial(
        self,
        ffmpeg: str,
        season: str,
        episodes: list[str],
        status,
    ) -> None:
        eps_data = self.result.seasons.get(season, {}).get("episodes", {})
        out_dir  = _get_download_dir(self.app) / _safe(self.result.title) / f"Season {int(season):02d}"
        out_dir.mkdir(parents=True, exist_ok=True)

        total = len(episodes)
        done  = 0
        for ep in sorted(episodes, key=lambda e: int(e) if e.isdigit() else 0):
            ep_link = eps_data.get(ep, "")
            if isinstance(ep_link, dict):
                ep_link = ep_link.get("link", "")
            if not ep_link:
                done += 1
                continue
            try:
                url = asyncio.run(self._resolve(self.token, ep_link, self.quality))
                if url:
                    out = out_dir / f"S{int(season):02d}E{int(ep):02d}.mp4"

                    def _prog(msg: str, d: int = done, t: int = total) -> None:
                        status(f"[{d+1}/{t}] {msg}")

                    self._ffmpeg(ffmpeg, url, out, f"Эп. {ep}", _prog)
                    done += 1
            except Exception as e:
                status(f"[red]Эп. {ep}: {e}[/red]")

        self._mark_downloaded()
        status(f"[green]Готово! {done}/{total} эпизодов → {out_dir}[/green]")

    def _download_movie(self, ffmpeg: str, status) -> None:
        out_dir = _get_download_dir(self.app)
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"{_safe(self.result.title)}.mp4"
        try:
            url = asyncio.run(self._resolve(self.token, self.result.link, self.quality))
            if url:
                self._ffmpeg(ffmpeg, url, out, self.result.title, status)
                self._mark_downloaded()
                status(f"[green]Готово! → {out}[/green]")
            else:
                status("[red]Не удалось получить ссылку[/red]")
        except Exception as e:
            status(f"[red]{e}[/red]")

    def _mark_downloaded(self) -> None:
        folder = self.app.db.get_folder_by_name("Скачано")
        if folder:
            self.app.db.add_to_folder(folder["id"], {
                "kodik_id":   self.result.id,
                "title":      self.result.title,
                "type":       self.result.type,
                "year":       self.result.year,
                "kodik_link": self.result.link,
                "poster_url": (self.result.material_data or {}).get("poster_url"),
            })

    # ── ffmpeg with real-time progress ───────────────────────────────────────

    @staticmethod
    def _ffmpeg(exe: str, url: str, output: Path, label: str, status_fn) -> bool:
        proc = subprocess.Popen(
            [
                exe, "-y",
                "-loglevel", "quiet",
                "-i", url,
                "-c", "copy",
                "-bsf:a", "aac_adtstoasc",
                "-progress", "pipe:1",
                str(output),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
        prog: dict[str, str] = {}
        for raw in proc.stdout:
            key, _, val = raw.strip().partition("=")
            if not key:
                continue
            prog[key] = val.strip()
            if key == "progress":
                size_mb  = int(prog.get("total_size", 0)) / 1_048_576
                out_time = prog.get("out_time", "")[:8]
                status_fn(f"{label}  •  {size_mb:.1f} МБ  •  видео {out_time}")
        proc.wait()
        return proc.returncode == 0

    @staticmethod
    async def _resolve(token: str, link: str, quality: str) -> str | None:
        async with KodikClient(token) as client:
            return await client.get_stream_url(link, preferred_quality=quality)
