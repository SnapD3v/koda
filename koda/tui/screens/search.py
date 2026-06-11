from textual.app import ComposeResult
from textual.screen import Screen
from textual.binding import Binding
from textual.widgets import Header, Footer, Input, ListView, ListItem, Label, Static, Button
from textual.containers import Vertical, Horizontal
from textual import work, on

from koda.api.kodik import SearchResult


class ResultItem(ListItem):
    """Один элемент в списке результатов."""

    def __init__(self, result: SearchResult) -> None:
        super().__init__()
        self.result = result

    def compose(self) -> ComposeResult:
        type_icons = {
            "movie": "🎬", "anime": "🎌", "serial": "📺",
            "anime-serial": "🎌", "cartoon-serial": "🎨",
            "foreign-movie": "🎬", "russian-movie": "🎬",
        }
        icon = type_icons.get(self.result.type, "▶")
        year = f"({self.result.year})" if self.result.year else ""
        translation = self.result.translation.title or ""

        yield Horizontal(
            Label(f"{icon} {self.result.title} {year}", classes="result-title"),
            Label(translation, classes="result-translation"),
            classes="result-row",
        )


_FILTER_TYPES: dict[str, str | None] = {
    "f-all":    None,
    "f-movie":  "movie",
    "f-serial": "serial",
    "f-anime":  "anime",
}

_MOVIE_TYPES  = {"movie", "foreign-movie", "russian-movie", "cartoon-movie", "documovie"}
_SERIAL_TYPES = {"serial", "foreign-serial", "russian-serial", "cartoon-serial", "docuserial"}
_ANIME_TYPES  = {"anime", "anime-serial"}


class SearchScreen(Screen):
    """Экран поиска."""

    BINDINGS = [
        Binding("escape",  "app.pop_screen", "Назад"),
        Binding("ctrl+l",  "app.library",    "Библиотека"),
    ]

    _search_timer = None
    _all_variants: dict = {}
    _scroll_index: int = 0
    _filter_type: str | None = None
    _next_page: str | None = None
    _last_query: str = ""

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Vertical(
            Input(
                placeholder="Поиск фильмов, сериалов, аниме...",
                id="search-input",
            ),
            Horizontal(
                Button("Все",       id="f-all",    classes="filter-btn filter-active"),
                Button("🎬 Фильмы", id="f-movie",  classes="filter-btn"),
                Button("📺 Сериалы", id="f-serial", classes="filter-btn"),
                Button("🎌 Аниме",  id="f-anime",  classes="filter-btn"),
                id="search-filters",
            ),
            Static("", id="search-status"),
            Button("✕ Очистить историю", id="search-clear-history", classes="hidden"),
            ListView(id="results-list"),
            Button("Загрузить ещё", id="search-load-more", classes="hidden"),
            id="search-container",
        )
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#search-input", Input).focus()
        self._show_history()

    def _show_history(self) -> None:
        history = self.app.db.get_history()
        results_list = self.query_one("#results-list", ListView)
        results_list.clear()
        self.query_one("#search-load-more", Button).add_class("hidden")

        clear_btn = self.query_one("#search-clear-history", Button)

        if not history:
            self.query_one("#search-status", Static).update("Начните вводить запрос для поиска")
            clear_btn.add_class("hidden")
            return

        self.query_one("#search-status", Static).update("Недавние запросы:")
        clear_btn.remove_class("hidden")
        for query in history:
            results_list.append(ListItem(Label(f"🕐 {query}"), name=query))

    @on(Input.Changed, "#search-input")
    def on_search_changed(self, event: Input.Changed) -> None:
        query = event.value.strip()

        if self._search_timer is not None:
            self._search_timer.stop()

        if not query:
            self._show_history()
            return
        self.query_one("#search-clear-history", Button).add_class("hidden")
        if len(query) < 2:
            self.query_one("#search-status", Static).update("Введите хотя бы 2 символа для поиска")
            return

        self.query_one("#search-status", Static).update("Поиск...")
        self._search_timer = self.set_timer(0.4, lambda: self._do_search(query))

    @on(Button.Pressed, ".filter-btn")
    def on_filter_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""
        if btn_id not in _FILTER_TYPES:
            return
        self._filter_type = _FILTER_TYPES[btn_id]
        for fid in _FILTER_TYPES:
            btn = self.query_one(f"#{fid}", Button)
            if fid == btn_id:
                btn.add_class("filter-active")
            else:
                btn.remove_class("filter-active")
        query = self.query_one("#search-input", Input).value.strip()
        if query and len(query) >= 2:
            self._do_search(query)

    @work(exclusive=True)
    async def _do_search(self, query: str) -> None:
        self._last_query = query
        self._next_page  = None
        try:
            results, next_page = await self.app.kodik.search(query, limit=100)
            self._next_page = next_page
            self._update_results(query, results, append=False)
        except Exception as e:
            self.query_one("#search-status", Static).update(f"[red]Ошибка: {e}[/red]")

    @work(exclusive=True)
    async def _do_load_more(self) -> None:
        if not self._next_page:
            return
        try:
            results, next_page = await self.app.kodik.search_next(self._next_page)
            self._next_page = next_page
            self._update_results(self._last_query, results, append=True)
        except Exception as e:
            self.query_one("#search-status", Static).update(f"[red]Ошибка: {e}[/red]")

    def _update_results(self, query: str, results: list[SearchResult], *, append: bool) -> None:
        seen: dict[tuple, list[SearchResult]] = {}

        if append:
            # keep existing variants
            seen = dict(self._all_variants)

        for r in results:
            if self._filter_type == "movie"  and r.type not in _MOVIE_TYPES:  continue
            if self._filter_type == "serial" and r.type not in _SERIAL_TYPES: continue
            if self._filter_type == "anime"  and r.type not in _ANIME_TYPES:  continue
            key = (r.title.lower(), r.year)
            seen.setdefault(key, []).append(r)

        if append:
            new_keys = {(r.title.lower(), r.year) for r in results}
            new_unique = [seen[k][0] for k in new_keys if k in seen]
        else:
            new_unique = [variants[0] for variants in seen.values()]

        self._all_variants = seen

        results_list = self.query_one("#results-list", ListView)
        load_more    = self.query_one("#search-load-more", Button)

        if not append and not new_unique:
            results_list.clear()
            self.query_one("#search-status", Static).update(
                f'Ничего не найдено по запросу "{query}"'
            )
            load_more.add_class("hidden")
            return

        total = len(self._all_variants)
        self.query_one("#search-status", Static).update(f"Найдено: {total}")

        if append:
            results_list.mount(*[ResultItem(r) for r in new_unique])
        else:
            results_list.clear()
            results_list.mount(*[ResultItem(r) for r in new_unique])
            self.app.db.add_to_history(query)

        if self._next_page:
            load_more.remove_class("hidden")
        else:
            load_more.add_class("hidden")

    @on(Button.Pressed, "#search-load-more")
    def on_load_more(self) -> None:
        self._do_load_more()

    @on(ListView.Selected)
    def on_result_selected(self, event: ListView.Selected) -> None:
        item = event.item

        if isinstance(item, ListItem) and not isinstance(item, ResultItem):
            self.query_one("#search-input", Input).value = item.name or ""
            return

        if isinstance(item, ResultItem):
            from koda.tui.screens.detail import DetailScreen
            key = (item.result.title.lower(), item.result.year)
            variants = self._all_variants.get(key, [item.result])
            self.app.push_screen(DetailScreen(item.result, variants))

    @on(Button.Pressed, "#search-clear-history")
    def on_clear_history(self) -> None:
        self.app.db.clear_history()
        self._show_history()
        self.app.notify("История очищена")

    def on_screen_suspend(self) -> None:
        lst = self.query_one("#results-list", ListView)
        self._scroll_index = lst.index or 0

    def on_screen_resume(self) -> None:
        lst = self.query_one("#results-list", ListView)
        if self._scroll_index and len(lst) > 0:
            try:
                lst.index = self._scroll_index
            except Exception:
                pass
        self.query_one("#search-input", Input).focus()
