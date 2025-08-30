# parser/lalafo_parser.py
import asyncio
import aiohttp
import logging
from typing import List, Dict, Tuple, Optional
from .get_phone_characters import extract_phone_info

logger = logging.getLogger(__name__)

BASE_URL = "https://lalafo.kg/api/search/v3/feed/search"
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "device": "pc"
}


async def fetch_json(session: aiohttp.ClientSession, params: dict) -> Optional[Dict]:
    """
    Запрос к API Lalafo.
    """
    try:
        async with session.get(BASE_URL, params=params, headers=HEADERS) as resp:
            if resp.status != 200:
                logger.warning(f"API вернул {resp.status} для {resp.url}, считаем что объявлений нет")
                return None
            return await resp.json()
    except Exception as e:
        logger.error(f"Ошибка при запросе {BASE_URL} с params={params}: {e}")
        return None


async def get_items_by_model(session: aiohttp.ClientSession,
                             model_id: int,
                             page: int = 1,
                             max_price: Optional[int] = None,
                             per_page: int = 20) -> List[Dict]:
    """
    Загружаем одну страницу объявлений по конкретной модели.
    """
    params = {
        "category_id": 1361,
        "expand": "url",
        "parameters[183][0]": model_id,
        "per-page": per_page,
        "with_feed_banner": "true",
        "page": page
    }
    if max_price is not None:
        params["price[to]"] = max_price

    data = await fetch_json(session, params)
    if not data or "items" not in data:
        return []
    return data.get("items", [])


async def get_all_items(model_id: int,
                        max_price: Optional[int] = None,
                        start_page: int = 1,
                        pages: int = 3) -> Tuple[List[Dict], int]:
    """
    Загружаем несколько страниц объявлений по модели.
    Автоостановка: прекращаем при пустой странице.
    Возвращает (объявления, следующая страница).
    """
    all_items: List[Dict] = []
    next_page = start_page + pages

    async with aiohttp.ClientSession() as session:
        for page in range(start_page, start_page + pages):
            items = await get_items_by_model(session, model_id, page=page, max_price=max_price)
            if not items:
                logger.info(f"Страница {page} пустая → конец объявлений.")
                return all_items, 1  # сброс на первую страницу
            all_items.extend(items)

    return all_items, next_page


def parse_lalafo_items(items: List[Dict]) -> List[Dict]:
    """
    Преобразуем объявления в удобный формат для БД и бота.
    """
    parsed_items = []
    for item in items:
        title = item.get("title", "")
        description = item.get("description", "")
        phone_info = extract_phone_info(title, description)
        price = item.get("price")

        parsed_items.append({
            "lalafo_id": item.get("id"),
            "title": title,
            "model": phone_info.get("model"),
            "new_price": price,
            "author_number": item.get("mobile"),
            "description": description,
            "city": item.get("city"),
            "storage": phone_info.get("storage"),
            "battery": phone_info.get("battery"),
            "color": phone_info.get("color"),
            "url": f"https://lalafo.kg{item.get('url')}"
        })
    return parsed_items


async def get_filtered_items(model_id: int,
                             max_price: Optional[int],
                             start_page: int = 1,
                             pages: int = 3) -> Tuple[List[Dict], int]:
    """
    Главная функция: тянем объявления по API и парсим.
    Возвращает (объявления, следующая страница).
    """
    all_items, next_page = await get_all_items(
        model_id, max_price, start_page=start_page, pages=pages
    )
    return parse_lalafo_items(all_items), next_page

