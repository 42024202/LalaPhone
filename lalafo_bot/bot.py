import os
import asyncio
import logging
from aiogram import Bot, Dispatcher
from utils.handlers import router as filters_router
from dotenv import load_dotenv  # если используешь .env файл

# Загружаем .env
load_dotenv()

logging.basicConfig(level=logging.INFO)

# Берём токен напрямую из окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден в окружении. Проверь .env")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
dp.include_router(filters_router)


async def main():
    try:
        print("🤖 Бот запущен и слушает апдейты...")
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())

