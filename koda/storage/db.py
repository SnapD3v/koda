import sqlite3
from pathlib import Path
from datetime import datetime, timezone


DB_PATH = Path.home() / ".config" / "koda" / "koda.db"


def _now() -> str:
    """Текущее время в ISO формате (UTC)."""
    return datetime.now(timezone.utc).isoformat()


class Database:

    def __init__(self, path: Path = DB_PATH) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        """Создаёт соединение с БД."""
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init(self) -> None:
        """Создаёт таблицы при первом запуске."""
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS folders (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    name       TEXT    NOT NULL UNIQUE,
                    created_at TEXT    NOT NULL
                );

                CREATE TABLE IF NOT EXISTS folder_items (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    folder_id  INTEGER NOT NULL
                                   REFERENCES folders(id) ON DELETE CASCADE,
                    kodik_id   TEXT    NOT NULL,
                    title      TEXT    NOT NULL,
                    type       TEXT    NOT NULL,
                    year       INTEGER,
                    kodik_link TEXT    NOT NULL,
                    poster_url TEXT,
                    added_at   TEXT    NOT NULL,
                    UNIQUE(folder_id, kodik_id)
                );

                CREATE TABLE IF NOT EXISTS progress (
                    kodik_id       TEXT    PRIMARY KEY,
                    season         INTEGER NOT NULL DEFAULT 1,
                    episode        INTEGER NOT NULL DEFAULT 1,
                    timecode       REAL    NOT NULL DEFAULT 0.0,
                    translation_id INTEGER NOT NULL DEFAULT 0,
                    updated_at     TEXT    NOT NULL
                );

                CREATE TABLE IF NOT EXISTS search_history (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    query       TEXT    NOT NULL,
                    searched_at TEXT    NOT NULL
                );
            """)
            try:
                conn.execute(
                    "ALTER TABLE progress ADD COLUMN translation_id INTEGER NOT NULL DEFAULT 0"
                )
            except sqlite3.OperationalError:
                pass

            try:
                conn.execute("ALTER TABLE folders ADD COLUMN sort_order INTEGER")
                conn.execute("UPDATE folders SET sort_order = id")
            except sqlite3.OperationalError:
                pass

            for name in ("Любимое", "Смотреть дальше", "Скачано"):
                conn.execute(
                    "INSERT OR IGNORE INTO folders (name, created_at) VALUES (?, ?)",
                    (name, _now()),
                )

    # ── Папки ───────────────────────────────────────────────────────────────

    def get_folder_by_name(self, name: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM folders WHERE name = ?", (name,)
            ).fetchone()
        return dict(row) if row else None

    def create_folder(self, name: str) -> int:
        """Создаёт папку и возвращает её id."""
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO folders (name, created_at) VALUES (?, ?)",
                (name, _now()),
            )
            return cur.lastrowid

    def delete_folder(self, folder_id: int) -> None:
        """Удаляет папку и весь её контент."""
        with self._connect() as conn:
            conn.execute("DELETE FROM folders WHERE id = ?", (folder_id,))

    def rename_folder(self, folder_id: int, new_name: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE folders SET name = ? WHERE id = ?",
                (new_name, folder_id),
            )

    def get_folders(self) -> list[dict]:
        """Возвращает все папки с количеством элементов в каждой."""
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT f.id, f.name, f.created_at, f.sort_order,
                       COUNT(fi.id) AS item_count
                FROM folders f
                LEFT JOIN folder_items fi ON fi.folder_id = f.id
                GROUP BY f.id
                ORDER BY COALESCE(f.sort_order, f.id), f.id
            """).fetchall()
        return [dict(r) for r in rows]

    def move_folder(self, folder_id: int, direction: int) -> None:
        """Меняет порядок папки: direction=-1 вверх, +1 вниз."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, COALESCE(sort_order, id) AS ord FROM folders ORDER BY ord, id"
            ).fetchall()
            ids = [r["id"] for r in rows]
            try:
                idx = ids.index(folder_id)
            except ValueError:
                return
            swap = idx + direction
            if swap < 0 or swap >= len(ids):
                return
            a_id, b_id = rows[idx]["id"], rows[swap]["id"]
            a_ord, b_ord = rows[idx]["ord"], rows[swap]["ord"]
            conn.execute("UPDATE folders SET sort_order = ? WHERE id = ?", (b_ord, a_id))
            conn.execute("UPDATE folders SET sort_order = ? WHERE id = ?", (a_ord, b_id))

    # ── Контент в папках ────────────────────────────────────────────────────

    def add_to_folder(self, folder_id: int, item: dict) -> None:
        """Добавляет контент в папку."""
        with self._connect() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO folder_items
                    (folder_id, kodik_id, title, type, year,
                     kodik_link, poster_url, added_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                folder_id,
                item["kodik_id"],
                item["title"],
                item["type"],
                item.get("year"),
                item["kodik_link"],
                item.get("poster_url"),
                _now(),
            ))

    def remove_from_folder(self, folder_id: int, kodik_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM folder_items WHERE folder_id=? AND kodik_id=?",
                (folder_id, kodik_id),
            )

    def get_folder_items(self, folder_id: int) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM folder_items WHERE folder_id=? ORDER BY added_at DESC",
                (folder_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def is_in_folder(self, folder_id: int, kodik_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM folder_items WHERE folder_id=? AND kodik_id=?",
                (folder_id, kodik_id),
            ).fetchone()
        return row is not None

    # ── Прогресс просмотра ──────────────────────────────────────────────────

    def save_progress(
        self,
        kodik_id: str,
        season: int = 1,
        episode: int = 1,
        timecode: float = 0.0,
        translation_id: int = 0,
    ) -> None:
        """Сохраняет или обновляет прогресс."""
        with self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO progress
                    (kodik_id, season, episode, timecode, translation_id, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (kodik_id, season, episode, timecode, translation_id, _now()))

    def get_progress(self, kodik_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM progress WHERE kodik_id = ?", (kodik_id,)
            ).fetchone()
        return dict(row) if row else None

    def get_all_progress(self) -> list[dict]:
        """Возвращает все записи прогресса — для экрана 'Продолжить просмотр'."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM progress ORDER BY updated_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_progress(self, kodik_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM progress WHERE kodik_id = ?", (kodik_id,))

    # ── История поиска ───────────────────────────────────────────────────────

    def add_to_history(self, query: str) -> None:
        """Добавляет запрос в историю."""
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM search_history WHERE query = ?", (query,)
            )
            conn.execute(
                "INSERT INTO search_history (query, searched_at) VALUES (?, ?)",
                (query, _now()),
            )
            conn.execute("""
                DELETE FROM search_history WHERE id NOT IN (
                    SELECT id FROM search_history ORDER BY searched_at DESC LIMIT 100
                )
            """)

    def get_history(self, limit: int = 20) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT query FROM search_history ORDER BY searched_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [r["query"] for r in rows]

    def clear_history(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM search_history")

    # ── Недавнее ────────────────────────────────────────────────────────────

    def get_recent_items(self, limit: int = 4) -> list[dict]:
        folder = self.get_folder_by_name("Смотреть дальше")
        if not folder:
            return []
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM folder_items WHERE folder_id = ? ORDER BY added_at DESC LIMIT ?",
                (folder["id"], limit),
            ).fetchall()
        return [dict(r) for r in rows]