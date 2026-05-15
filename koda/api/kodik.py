import re
import json
import base64
import httpx

from dataclasses import dataclass, field
from typing import Optional

from urllib.parse import unquote

# ─────────────────────────────────────────────
# Константы
# ─────────────────────────────────────────────
API_BASE     = "https://kodik-api.com"
REFERER      = "https://example.com"   # любой домен
USER_AGENT   = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


# ─────────────────────────────────────────────
# Модели данных
# ─────────────────────────────────────────────
@dataclass
class Translation:
    id:    int
    title: str
    type:  str

@dataclass
class SearchResult:
    id:           str
    type:         str
    title:        str
    title_orig:   str
    year:         int
    link:         str
    quality:      str
    translation:  Translation
    seasons:      dict         = field(default_factory=dict)
    kinopoisk_id: Optional[str] = None
    imdb_id:      Optional[str] = None
    material_data: dict        = field(default_factory=dict)


# ─────────────────────────────────────────────
# Клиент
# ─────────────────────────────────────────────
class KodikClient:

    def __init__(self, token: str) -> None:
        self.token = token
        self._http = httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
            timeout=15.0,
        )

    # ── Публичный интерфейс ──────────────────

    async def search(
        self,
        query: str,
        media_type: Optional[str] = None,
        limit: int = 20,
    ) -> list[SearchResult]:
        """Поиск контента через Kodik API."""
        params: dict = {
            "token":              self.token,
            "title":              query,
            "with_material_data": "true",
            "limit":              limit,
        }
        if media_type:
            params["type"] = media_type

        response = await self._http.post(f"{API_BASE}/search", data=params)
        response.raise_for_status()

        data = response.json()
        return [self._parse_result(r) for r in data.get("results", [])]

    async def get_stream_url(
        self,
        link: str,
        preferred_quality: str = "720",
    ) -> Optional[str]:
        """
        Полный пайплайн: ссылка на плеер → настоящий .m3u8 URL.
        Это единственный метод который нужен снаружи класса.
        """
        # Шаг 1: нормализуем ссылку
        if link.startswith("//"):
            link = "https:" + link

        player_domain = link.split("/")[2]

        # Шаг 2: получаем HTML плеера
        html = await self._fetch_player_page(link)

        # Шаг 3: вытаскиваем urlParams из JS
        url_params = self._extract_url_params(html)

        # Шаг 4: POST /ftor → получаем закодированные ссылки
        links = await self._fetch_links(player_domain, url_params, player_url=link)

        # Шаг 5: декодируем и выбираем качество
        return self._pick_best_url(links, preferred_quality)

    # ── Приватные методы ─────────────────────

    def _parse_player_url(self, url: str) -> dict:
        parts = url.rstrip("/").split("/")
        return {
            "type": parts[3],
            "id":   parts[4],
            "hash": parts[5],
        }

    async def _fetch_player_page(self, url: str) -> str:
        response = await self._http.get(
            url,
            headers={"Referer": REFERER},
        )
        response.raise_for_status()
        return response.text

    def _extract_url_params(self, html: str) -> dict:
        match = re.search(r"var urlParams\s*=\s*'(\{.+?\})'", html)
        if not match:
            raise ValueError("urlParams не найден в HTML плеера")
        return json.loads(match.group(1))

    async def _fetch_links(
        self,
        player_domain: str,
        params: dict,
        player_url: str,
    ) -> dict:
        url_parts = self._parse_player_url(player_url)

        clean_params = {
            k: str(v).lower() if isinstance(v, bool) else v
            for k, v in params.items()
        }

        if "ref" in clean_params:
            clean_params["ref"] = unquote(clean_params["ref"])

        clean_params.update({
            "type":           url_parts["type"],
            "hash":           url_parts["hash"],
            "id":             url_parts["id"],
            "bad_user":       "false",
            "cdn_is_working": "true",
            "info":           "{}",
        })

        response = await self._http.post(
            f"https://{player_domain}/ftor",
            data=clean_params,
            headers={
                "Referer":          player_url,
                "Origin":           f"https://{player_domain}",
                "X-Requested-With": "XMLHttpRequest",
            },
        )

        response.raise_for_status()
        return response.json().get("links", {})

    def _decode_url(self, encoded: str) -> str:
        """
        Kodik кодирует URL так:
        1. Стандартный base64 encode URL
        2. Каждая буква сдвигается на +8 по алфавиту (ROT-8)
        """
        # Шаг 1: обратный ROT-8 — возвращаем стандартный base64
        std_b64 = ""
        for c in encoded:
            if 'A' <= c <= 'Z':
                std_b64 += chr((ord(c) - ord('A') - 8) % 26 + ord('A'))
            elif 'a' <= c <= 'z':
                std_b64 += chr((ord(c) - ord('a') - 8) % 26 + ord('a'))
            else:
                std_b64 += c

        # Шаг 2: base64 decode (добиваем паддинг если нужно)
        padding = "=" * (4 - len(std_b64) % 4) if len(std_b64) % 4 else ""
        decoded = base64.b64decode(std_b64 + padding).decode("utf-8")

        # Шаг 3: добавляем схему если нужно
        if decoded.startswith("//"):
            decoded = "https:" + decoded

        return decoded

    def _pick_best_url(
        self,
        links: dict,
        preferred: str = "720",
    ) -> Optional[str]:
        """Выбирает лучшее доступное качество из ответа /ftor."""
        priority = [preferred, "720", "480", "360", "1080"]
        for quality in priority:
            if quality in links and links[quality]:
                encoded_src = links[quality][0]["src"]
                return self._decode_url(encoded_src)
        return None

    def _parse_result(self, raw: dict) -> SearchResult:
        tr = raw.get("translation", {})
        return SearchResult(
            id           = raw["id"],
            type         = raw["type"],
            title        = raw.get("title", ""),
            title_orig   = raw.get("title_orig", ""),
            year         = raw.get("year", 0),
            link         = raw["link"],
            quality      = raw.get("quality", ""),
            translation  = Translation(
                id    = tr.get("id", 0),
                title = tr.get("title", ""),
                type  = tr.get("type", ""),
            ),
            seasons       = raw.get("seasons", {}),
            kinopoisk_id  = raw.get("kinopoisk_id"),
            imdb_id       = raw.get("imdb_id"),
            material_data = raw.get("material_data", {}),
        )

    # ── Context manager ──────────────────────

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self._http.aclose()