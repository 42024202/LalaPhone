# parser/tests_lalafo.py
import asyncio
import logging
from parser.lalafo_parser import get_items_by_model, get_all_items, get_filtered_items
import aiohttp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MODEL_ID = 32992   # пример iPhone модели (замени на нужную из MODEL_TO_PARAM)
MAX_PRICE = 50000
PAGES = 3


async def test_one_page():
    async with aiohttp.ClientSession() as session:
        items = await get_items_by_model(session, model_id=MODEL_ID, page=1, max_price=MAX_PRICE)
        print(f"[ONE PAGE] Загружено {len(items)} объявлений")
        if items:
            print("Пример объявления:", items[0])


async def test_all_pages():
    items, next_page = await get_all_items(model_id=MODEL_ID,
                                           max_price=MAX_PRICE,
                                           start_page=1,
                                           pages=PAGES)
    print(f"[ALL PAGES] Загружено {len(items)} объявлений за {PAGES} страниц, next_page={next_page}")


async def test_filtered_items_cycle():
    # допустим, в БД хранится last_page = 1
    start_page = 1
    ads, next_page = await get_filtered_items(MODEL_ID, MAX_PRICE, start_page=start_page, pages=PAGES)
    print(f"[FILTERED] {len(ads)} объявлений, следующая страница {next_page}")

    # теперь симулируем, что мы на большой пустой странице
    fake_start = 55555
    ads, next_page = await get_filtered_items(MODEL_ID, MAX_PRICE, start_page=fake_start, pages=1)
    print(f"[CYCLE TEST] start_page={fake_start}, получили {len(ads)} объявлений, next_page={next_page}")
    if next_page == 1:
        print("✅ Автоциклический сброс работает: после пустой страницы возвращаемся на page=1")


async def main():
    await test_one_page()
    await test_all_pages()
    await test_filtered_items_cycle()


if __name__ == "__main__":
    asyncio.run(main())

