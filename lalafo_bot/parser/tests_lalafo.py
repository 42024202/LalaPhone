import asyncio
import logging
from parser.lalafo_parser import get_items_by_model, get_all_items, get_filtered_items
import aiohttp

# Настройка логов
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MODEL_ID = 32992
MAX_PRICE = 50000
PAGES = 10

async def test_one_page():
    async with aiohttp.ClientSession() as session:
        items = await get_items_by_model(session, model_id=MODEL_ID, page=1)
        print(f"[ONE PAGE] Загружено {len(items)} объявлений на первой странице")
        if items:
            print("Пример:", items[0])

async def test_all_pages():
    items = await get_all_items(model_id=MODEL_ID, max_price=MAX_PRICE, pages=PAGES)
    print(f"[ALL PAGES] Загружено всего {len(items)} объявлений за максимум {PAGES} страниц")
    if not items:
        print("Пустые страницы сработали, автоостановка прошла корректно")

async def test_filtered_items():
    items = await get_filtered_items(model_id=MODEL_ID, max_price=MAX_PRICE, pages=5)
    print(f"[FILTERED] Всего после парсинга: {len(items)}")
    if items:
        print("Пример после парсинга:", items[0])

async def main():
    await test_one_page()
    await test_all_pages()
    await test_filtered_items()

if __name__ == "__main__":
    asyncio.run(main())

