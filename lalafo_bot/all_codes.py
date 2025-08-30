"""Получаем жсон. Файл lalafo_api.py"""
import aiohttp

BASE_URL = "https://lalafo.kg/api/search/v3/feed/search"
HEADERS = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "device": "pc"
        }

async def fetch_json(url: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=HEADERS) as resp:
            resp.raise_for_status()
            return await resp.json()

async def get_first_page(filters: dict):
    url = f"{BASE_URL}?category_id=1361&expand=url&per-page=20&with_feed_banner=true&page=1"
    data = await fetch_json(url)
    return data

async def get_next_page(next_url: str):
    if not next_url:
        return None
    data = await fetch_json(next_url)
    return data

"""Получаем модель колор итд. Файл get_phone_characters.py"""
import re

COLORS = [
    "черный", "белый", "синий", "красный", "зеленый", "желтый", "розовый", "фиолетовый", "серый",
    "black", "white", "blue", "red", "green", "yellow", "pink", "purple", "gray", "silver", "gold"
]

STORAGE_PATTERN = re.compile(r"(\d+\s*(ГБ|GB))", re.IGNORECASE)
BATTERY_PATTERN = re.compile(r"(\d{1,3}\s*%)")

def extract_phone_info(title: str) -> dict:
    if not title:
        return {"model": "", "storage": None, "battery": None, "color": None}

    parts = [p.strip() for p in title.split(",")]

    storage = None
    battery = None
    color = None
    model_parts = []

    for part in parts:
        if storage is None:
            match_storage = STORAGE_PATTERN.search(part)
            if match_storage:
                storage = match_storage.group(1)
                continue

        if battery is None:
            match_battery = BATTERY_PATTERN.search(part)
            if match_battery:
                battery = match_battery.group(1)
                continue

        if color is None:
            for c in COLORS:
                if c.lower() in part.lower():
                    color = c
                    break
            if color:
                continue

        model_parts.append(part)

    model = " ".join(model_parts).strip()

    return {
        "model": model,
        "storage": storage,
        "battery": battery,
        "color": color
    }


"""Парсим сами данные полученные из джсона. Файл lalafo_parser.py"""
from __future__ import annotations
from get_phone_characters import extract_phone_info


def parse_lalafo_items(items: list[dict]) -> list[dict]:
    parsed_items = []
    for item in items:
        title = item.get("title", "")
        phone_info = extract_phone_info(title) or {}

        parsed_item = {
            "lalafo_id": item.get("id"),
            "title": title,
            "model": phone_info.get("model"),
            "old_price": item.get("old_price"),
            "new_price": item.get("price"),
            "author_number": item.get("mobile"),
            "description": item.get("description"),
            "city": item.get("city"),
            "created_at": item.get("created_time"),
            "storage": phone_info.get("storage"),
            "battery": phone_info.get("battery"),
            "color": phone_info.get("color")
        }
        parsed_items.append(parsed_item)
    return parsed_items


"""Фильтры. Файл.фильтерс.пай"""
def filter_items(items, min_price=None, max_price=None, models=None, keywords=None):
    filtered = []
    keywords = ["срочно", "обмен", "торг уместен"]
    for item in items:
        price = item.get("new_price")
        model = item.get("model")
        title = item.get("title", "")
        description = item.get("description", "")

        if min_price is not None and (price is None or price < min_price):
            continue
        if max_price is not None and (price is None or price > max_price):
            continue

        if models and model not in models:
            continue

        if keywords:
            combined_text = f"{title} {description}".lower()
            if not any(word.lower() in combined_text for word in keywords):
                continue

        filtered.append(item)
    return filtered



