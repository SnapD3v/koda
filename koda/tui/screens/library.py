from textual.app import ComposeResult
from textual.screen import Screen, ModalScreen
from textual.binding import Binding
from textual.widgets import Header, Footer, Label, Button, Static, ListView, ListItem, Input, ContentSwitcher
from textual.containers import Vertical
from textual import on, work

from koda.api.kodik import SearchResult, Translation


# ── Custom list items ────────────────────────────────────────────────────────

class FolderItem(ListItem):
    def __init__(self, folder: dict) -> None:
        super().__init__()
        self.folder = folder

    def compose(self) -> ComposeResult:
        count = self.folder.get("item_count", 0)
        yield Label(f"📁 {self.folder['name']}  ({count} эл.)")


class FolderContentItem(ListItem):
    def __init__(self, item: dict, progress: dict | None = None) -> None:
        super().__init__()
        self.item = item
        self._progress = progress

    def compose(self) -> ComposeResult:
        icons = {
            "movie": "🎬", "serial": "📺", "anime": "🎌",
            "anime-serial": "🎌", "cartoon-serial": "🎨",
            "foreign-movie": "🎬", "russian-movie": "🎬",
        }
        icon = icons.get(self.item.get("type", ""), "▶")
        year = f"({self.item['year']})" if self.item.get("year") else ""

        prog_text = ""
        if self._progress and (self._progress.get("timecode") or 0) > 5:
            s = self._progress.get("season", 1)
            e = self._progress.get("episode", 1)
            tc = int(self._progress["timecode"])
            mins, secs = tc // 60, tc % 60
            is_series = self.item.get("type") not in ("movie", "foreign-movie", "russian-movie")
            if is_series:
                prog_text = f"  [dim]▶ С{s}Е{e} {mins}:{secs:02d}[/dim]"
            else:
                prog_text = f"  [dim]▶ {mins}:{secs:02d}[/dim]"

        yield Label(f"{icon} {self.item['title']} {year}{prog_text}")


# ── New-folder modal ─────────────────────────────────────────────────────────

class NewFolderModal(ModalScreen):
    """Small modal that returns the typed folder name, or None on cancel."""

    BINDINGS = [Binding("escape", "cancel", "Отмена")]

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("Название папки:", id="nfm-title"),
            Input(placeholder="Введите название...", id="nfm-input"),
            Button("Создать", id="nfm-create", variant="primary"),
            Button("Отмена",  id="nfm-cancel", variant="default"),
            id="nfm-container",
        )

    def action_cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#nfm-create")
    def on_create(self) -> None:
        name = self.query_one("#nfm-input", Input).value.strip()
        self.dismiss(name if name else None)

    @on(Button.Pressed, "#nfm-cancel")
    def on_cancel_btn(self) -> None:
        self.dismiss(None)


# ── Main screen ──────────────────────────────────────────────────────────────

_SYSTEM_FOLDERS = frozenset({"Любимое", "Скачано", "Смотреть дальше"})


class LibraryScreen(Screen):
    """Экран библиотеки: папки и их содержимое."""

    BINDINGS = [
        Binding("escape",   "back_or_close", "Назад"),
        Binding("n",        "new_folder",    "Новая папка"),
        Binding("d",        "delete",        "Удалить"),
        Binding("alt+up",   "folder_up",   "Вверх", show=False, priority=True),
        Binding("alt+down", "folder_down", "Вниз",  show=False, priority=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._current_folder: dict | None = None
        self._folder_items: list[dict] = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield Vertical(
            Static("", id="lib-status"),
            Input(placeholder="Поиск в библиотеке...", id="lib-search", classes="hidden"),
            ContentSwitcher(
                ListView(id="lib-folders"),
                ListView(id="lib-items"),
                initial="lib-folders",
            ),
            id="lib-container",
        )
        yield Footer()

    def on_mount(self) -> None:
        self._load_folders()

    # ── Data loading ─────────────────────────────────────────────────────────

    def _load_folders(self) -> None:
        folders = self.app.db.get_folders()
        lst = self.query_one("#lib-folders", ListView)
        lst.clear()
        if folders:
            for f in folders:
                lst.append(FolderItem(f))
            self.query_one("#lib-status", Static).update(
                f"Папок: {len(folders)}  •  N — создать  •  D — удалить  •  Alt+↑↓ — порядок"
            )
        else:
            self.query_one("#lib-status", Static).update(
                "Папок нет.  Нажмите N чтобы создать первую."
            )

    def _load_items(self, folder_id: int) -> None:
        self._folder_items = self.app.db.get_folder_items(folder_id)
        self._render_items(self._folder_items)

    def _render_items(self, items: list[dict]) -> None:
        lst = self.query_one("#lib-items", ListView)
        lst.clear()
        folder_name = self._current_folder["name"] if self._current_folder else ""
        if items:
            for item in items:
                progress = self.app.db.get_progress(item["kodik_id"])
                lst.append(FolderContentItem(item, progress))
            self.query_one("#lib-status", Static).update(
                f"[bold]{folder_name}[/bold]  •  {len(items)} эл.  •  Escape — назад"
            )
        else:
            q = self.query_one("#lib-search", Input).value.strip()
            msg = f'Ничего не найдено по "{q}"' if q else "Папка пуста."
            self.query_one("#lib-status", Static).update(
                f"[bold]{folder_name}[/bold]  •  {msg}  •  Escape — назад"
            )

    def _filter_items(self, query: str) -> None:
        if not query:
            self._render_items(self._folder_items)
            return
        q = query.lower()
        self._render_items([i for i in self._folder_items if q in i["title"].lower()])

    # ── List events ──────────────────────────────────────────────────────────

    @on(ListView.Selected, "#lib-folders")
    def on_folder_selected(self, event: ListView.Selected) -> None:
        if not isinstance(event.item, FolderItem):
            return
        self._current_folder = event.item.folder
        self._load_items(self._current_folder["id"])
        self.query_one(ContentSwitcher).current = "lib-items"
        self.query_one("#lib-search", Input).remove_class("hidden")

    @on(ListView.Selected, "#lib-items")
    def on_item_selected(self, event: ListView.Selected) -> None:
        if not isinstance(event.item, FolderContentItem):
            return
        self._open_detail(event.item.item)

    @on(Input.Changed, "#lib-search")
    def on_lib_search_changed(self, event: Input.Changed) -> None:
        self._filter_items(event.value.strip())

    @work
    async def _open_detail(self, item: dict) -> None:
        from koda.tui.screens.detail import DetailScreen

        if self._current_folder and self._current_folder["name"] == "Скачано":
            from koda.tui.screens.download import LocalFilesScreen
            self.app.push_screen(LocalFilesScreen(item))
            return

        self.query_one("#lib-status", Static).update("Загрузка...")
        full_result = None
        variants: list = []
        try:
            results = await self.app.kodik.search(item["title"], limit=25)
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

    # ── Key actions ──────────────────────────────────────────────────────────

    def action_back_or_close(self) -> None:
        if self._current_folder is not None:
            self._current_folder = None
            self._folder_items = []
            search = self.query_one("#lib-search", Input)
            search.value = ""
            search.add_class("hidden")
            self.query_one(ContentSwitcher).current = "lib-folders"
            self._load_folders()
        else:
            self.app.pop_screen()

    @work
    async def action_new_folder(self) -> None:
        name = await self.app.push_screen_wait(NewFolderModal())
        if not name:
            return
        if name in _SYSTEM_FOLDERS:
            self.app.notify(f'"{name}" — системная папка, нельзя создать вручную', severity="warning")
            return
        try:
            self.app.db.create_folder(name)
        except Exception:
            self.app.notify(f'Папка "{name}" уже существует', severity="warning")
            return
        self.app.notify(f'Папка "{name}" создана')
        self._load_folders()

    def action_delete(self) -> None:
        switcher = self.query_one(ContentSwitcher)
        if switcher.current == "lib-folders":
            lst = self.query_one("#lib-folders", ListView)
            highlighted = lst.highlighted_child
            if not isinstance(highlighted, FolderItem):
                return
            folder = highlighted.folder
            if folder["name"] in _SYSTEM_FOLDERS:
                self.app.notify("Системные папки нельзя удалить", severity="warning")
                return
            self.app.db.delete_folder(folder["id"])
            self.app.notify(f'Папка "{folder["name"]}" удалена')
            self._load_folders()
        elif switcher.current == "lib-items" and self._current_folder:
            lst = self.query_one("#lib-items", ListView)
            highlighted = lst.highlighted_child
            if not isinstance(highlighted, FolderContentItem):
                return
            item = highlighted.item
            self.app.db.remove_from_folder(self._current_folder["id"], item["kodik_id"])
            self.app.notify(f'"{item["title"]}" удалено из папки')
            self._folder_items = [i for i in self._folder_items if i["kodik_id"] != item["kodik_id"]]
            self._filter_items(self.query_one("#lib-search", Input).value.strip())

    def action_folder_up(self) -> None:
        if self._current_folder is not None:
            return
        lst = self.query_one("#lib-folders", ListView)
        highlighted = lst.highlighted_child
        if not isinstance(highlighted, FolderItem):
            return
        self.app.db.move_folder(highlighted.folder["id"], -1)
        self._load_folders()

    def action_folder_down(self) -> None:
        if self._current_folder is not None:
            return
        lst = self.query_one("#lib-folders", ListView)
        highlighted = lst.highlighted_child
        if not isinstance(highlighted, FolderItem):
            return
        self.app.db.move_folder(highlighted.folder["id"], 1)
        self._load_folders()
