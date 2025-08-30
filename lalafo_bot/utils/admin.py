from aiogram import Router, F
from aiogram.types import Message
from database.session import AsyncSessionLocal
from utils.check_ads import process_filters

router = Router()

@router.message(F.text == "/force_check")
async def cmd_force_check(message: Message):
    """
    Ручная проверка всех фильтров (для тестов).
    """
    await message.answer("🔄 Начинаю проверку фильтров...")

    try:
        # дергаем process_filters вручную
        await process_filters(message.bot)
        await message.answer("✅ Проверка завершена.")
    except Exception as e:
        await message.answer(f"⚠ Ошибка: {e}")

