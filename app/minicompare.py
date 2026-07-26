from __future__ import annotations

import asyncio
from dataclasses import dataclass
from time import monotonic
from urllib.parse import urlparse

import httpx


MINICOMPARE_CATALOG_URL = "https://minicompare.info/includes/_data.php?r4"
MINICOMPARE_HOST = "minicompare.info"
MINICOMPARE_IMAGE_PATH_PREFIX = "/assets/collection/"
MINICOMPARE_SOURCE_URL = "https://minicompare.info/"
CATALOG_CACHE_SECONDS = 6 * 60 * 60
MAX_CATALOG_BYTES = 5 * 1024 * 1024
MAX_IMAGE_BYTES = 15 * 1024 * 1024
REQUEST_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Plinthmaker/1.0 (+https://plinthmaker.thehivemind5.com)",
}


class MiniCompareUnavailableError(RuntimeError):
    pass


class MiniCompareMiniNotFoundError(LookupError):
    pass


@dataclass(frozen=True)
class MiniCompareMini:
    id: str
    name: str
    collection: str
    image_url: str
    search_text: str


@dataclass(frozen=True)
class MiniCompareImage:
    content: bytes
    media_type: str


def humanize_slug(value: str) -> str:
    return " ".join(value.replace("_", " ").replace("-", " ").split()).title()


def validate_image_url(image_url: str) -> bool:
    parsed = urlparse(image_url)
    return (
        parsed.scheme == "https"
        and parsed.hostname == MINICOMPARE_HOST
        and parsed.path.startswith(MINICOMPARE_IMAGE_PATH_PREFIX)
        and parsed.path.lower().endswith((".webp", ".png", ".jpg", ".jpeg"))
        and parsed.query == ""
        and parsed.fragment == ""
    )


def parse_catalog(catalog: object) -> list[MiniCompareMini]:
    if not isinstance(catalog, dict):
        raise MiniCompareUnavailableError("MiniCompare returned an invalid catalog")

    minis_by_id: dict[str, MiniCompareMini] = {}

    def visit(node: dict[object, object], path: tuple[str, ...]) -> None:
        for raw_key, value in node.items():
            if not isinstance(raw_key, str):
                continue

            current_path = (*path, raw_key)
            if isinstance(value, dict):
                visit(value, current_path)
                continue

            if not isinstance(value, str) or not validate_image_url(value):
                continue

            if not path or path[0].startswith("_"):
                continue

            name = humanize_slug(raw_key)
            collection = " › ".join(humanize_slug(part) for part in path)
            search_text = " ".join(
                [raw_key, name, collection, *(part.replace("-", " ") for part in path)]
            ).lower()
            minis_by_id[raw_key] = MiniCompareMini(
                id=raw_key,
                name=name,
                collection=collection,
                image_url=value,
                search_text=search_text,
            )

    visit(catalog, ())
    return sorted(
        minis_by_id.values(),
        key=lambda mini: (mini.name.casefold(), mini.collection.casefold(), mini.id),
    )


class MiniCompareCatalog:
    def __init__(
        self,
        *,
        catalog_url: str = MINICOMPARE_CATALOG_URL,
        cache_seconds: float = CATALOG_CACHE_SECONDS,
        timeout_seconds: float = 15.0,
    ) -> None:
        self.catalog_url = catalog_url
        self.cache_seconds = cache_seconds
        self.timeout_seconds = timeout_seconds
        self._items: list[MiniCompareMini] = []
        self._items_by_id: dict[str, MiniCompareMini] = {}
        self._loaded_at = 0.0
        self._lock = asyncio.Lock()

    async def _load_items(self) -> list[MiniCompareMini]:
        if self._items and monotonic() - self._loaded_at < self.cache_seconds:
            return self._items

        async with self._lock:
            if self._items and monotonic() - self._loaded_at < self.cache_seconds:
                return self._items

            try:
                async with httpx.AsyncClient(
                    follow_redirects=False,
                    timeout=self.timeout_seconds,
                ) as client:
                    response = await client.get(self.catalog_url, headers=REQUEST_HEADERS)
                response.raise_for_status()
            except httpx.HTTPError as error:
                raise MiniCompareUnavailableError(
                    "MiniCompare's catalog is temporarily unavailable"
                ) from error

            if len(response.content) > MAX_CATALOG_BYTES:
                raise MiniCompareUnavailableError("MiniCompare returned an oversized catalog")

            try:
                parsed_items = parse_catalog(response.json())
            except ValueError as error:
                raise MiniCompareUnavailableError(
                    "MiniCompare returned an invalid catalog"
                ) from error

            if not parsed_items:
                raise MiniCompareUnavailableError("MiniCompare returned an empty catalog")

            self._items = parsed_items
            self._items_by_id = {mini.id: mini for mini in parsed_items}
            self._loaded_at = monotonic()
            return self._items

    async def search(self, query: str, *, limit: int = 100) -> list[MiniCompareMini]:
        items = await self._load_items()
        normalized_query = " ".join(query.casefold().split())
        tokens = normalized_query.split()
        if not tokens:
            return []

        matches = [
            mini for mini in items if all(token in mini.search_text for token in tokens)
        ]

        def rank(mini: MiniCompareMini) -> tuple[int, str, str]:
            name = mini.name.casefold()
            if name == normalized_query:
                match_rank = 0
            elif name.startswith(normalized_query):
                match_rank = 1
            elif normalized_query in name:
                match_rank = 2
            else:
                match_rank = 3
            return match_rank, name, mini.collection.casefold()

        matches.sort(key=rank)
        return matches[:limit]

    async def get_mini(self, mini_id: str) -> MiniCompareMini:
        await self._load_items()
        mini = self._items_by_id.get(mini_id)
        if mini is None:
            raise MiniCompareMiniNotFoundError(mini_id)
        return mini

    async def get_image(self, mini_id: str) -> MiniCompareImage:
        mini = await self.get_mini(mini_id)
        try:
            async with httpx.AsyncClient(
                follow_redirects=False,
                timeout=self.timeout_seconds,
            ) as client:
                response = await client.get(
                    mini.image_url,
                    headers={
                        "Accept": "image/avif,image/webp,image/png,image/jpeg",
                        "User-Agent": REQUEST_HEADERS["User-Agent"],
                    },
                )
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise MiniCompareUnavailableError(
                "MiniCompare's image is temporarily unavailable"
            ) from error

        media_type = response.headers.get("content-type", "").split(";", 1)[0].strip()
        if not media_type.startswith("image/"):
            raise MiniCompareUnavailableError("MiniCompare returned an invalid image")
        if len(response.content) > MAX_IMAGE_BYTES:
            raise MiniCompareUnavailableError("MiniCompare returned an oversized image")

        return MiniCompareImage(content=response.content, media_type=media_type)
