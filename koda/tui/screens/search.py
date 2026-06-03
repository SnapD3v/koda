from textual.app import ComposeResult
from textual.screen import Screen
from textual.binding import Binding
from textual.widgets import Header, Footer, Input, ListView, ListItem, Label, Static, Button
from textual.containers import Vertical, Horizontal
from textual import work, on

from koda.api.kodik import KodikClient, SearchResult


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


class SearchScreen(Screen):
    """Экран поиска — стартовый экран приложения."""

    BINDINGS = [
        Binding("escape",  "app.pop_screen", "Назад"),
        Binding("ctrl+l",  "app.library",    "Библиотека"),
    ]

    _search_timer = None
    _all_variants: dict = {}
    _scroll_index: int = 0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Vertical(
            Input(
                placeholder="Поиск фильмов, сериалов, аниме...",
                id="search-input",
            ),
            Static("", id="search-status"),
            Button("✕ Очистить историю", id="search-clear-history", classes="hidden"),
            ListView(id="results-list"),
            id="search-container",
        )
        yield Footer()

    def on_mount(self) -> None:
        """При открытии — фокус на строку поиска и показать историю."""
        self.query_one("#search-input", Input).focus()
        self._show_history()

    def _show_history(self) -> None:
        """Показывает последние запросы когда строка поиска пустая."""
        history = self.app.db.get_history()
        results_list = self.query_one("#results-list", ListView)
        results_list.clear()

        clear_btn = self.query_one("#search-clear-history", Button)

        if not history:
            self.query_one("#search-status", Static).update(
                "Начните вводить запрос для поиска"
            )
            clear_btn.add_class("hidden")
            return

        self.query_one("#search-status", Static).update("Недавние запросы:")
        clear_btn.remove_class("hidden")
        for query in history:
            results_list.append(ListItem(Label(f"🕐 {query}"), name=query))

    @on(Input.Changed, "#search-input")
    def on_search_changed(self, event: Input.Changed) -> None:
        """Запускает поиск при каждом изменении строки (с небольшой задержкой)."""
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

    @work(exclusive=True)
    async def _do_search(self, query: str) -> None:
        try:
            results = await self.app.kodik.search(query, limit=100)
            self._update_results(query, results)
        except Exception as e:
            self.query_one("#search-status", Static).update(
                f"[red]Ошибка: {e}[/red]"
            )

    def _update_results(self, query: str, results: list[SearchResult]) -> None:
        seen: dict[tuple, list[SearchResult]] = {}
        for r in results:
            key = (r.title.lower(), r.year)
            seen.setdefault(key, []).append(r)

        unique = [variants[0] for variants in seen.values()]
        self._all_variants = seen

        results_list = self.query_one("#results-list", ListView)

        if not unique:
            results_list.clear()
            self.query_one("#search-status", Static).update(
                f'Ничего не найдено по запросу "{query}"'
            )
            return

        self.query_one("#search-status", Static).update(f"Найдено: {len(unique)}")
        items = [ResultItem(r) for r in unique]
        results_list.clear()
        results_list.mount(*items)
        self.app.db.add_to_history(query)

    @on(ListView.Selected)
    def on_result_selected(self, event: ListView.Selected) -> None:
        """Открывает DetailScreen при выборе результата."""
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
            lst.move_cursor(row=self._scroll_index)
        self.query_one("#search-input", Input).focus()