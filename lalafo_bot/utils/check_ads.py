import logging
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession
from database.session import AsyncSessionLocal
from utils.services_for_filters import add_ad_to_filter, update_last_page, get_all_filters
from parser.model_to_param import MODEL_TO_PARAM
from parser.lalafo_parser import get_filtered_items

logger = logging.getLogger(__name__)


async def send_safe(bot: Bot, user_id: int, text: str):
    """Безопасная отправка сообщений пользователю"""
    try:
        await bot.send_message(chat_id=user_id, text=text)
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения {user_id}: {e}")


async def process_single_filter(
    session: AsyncSession,
    bot: Bot,
    flt,
    pages_per_run: int,
    send_empty: bool = False,
):
    """
    Обрабатывает один фильтр:
    - Берёт last_page из БД (или 1),
    - Загружает N страниц подряд,
    - Если встречает пустую страницу → сбрасывает last_page = 1,
    - Иначе сохраняет last_page = следующая страница,
    - Шлёт новые объявления или уведомление об отсутствии новых (если send_empty=True).
    """
    model_param = MODEL_TO_PARAM.get(flt.model)
    if not model_param:
        return

    start_page = flt.last_page or 1

    ads, next_page = await get_filtered_items(
        model_param,
        max_price=flt.max_price,
        start_page=start_page,
        pages=pages_per_run,
    )

    if not ads:
        await update_last_page(session, flt.id, 1)
        await session.commit()
        if send_empty:
            await send_safe(bot, flt.user_id, f"ℹ️ По фильтру «{flt.model}» новых объявлений нет.")
        return

    new_ads_count = 0
    for ad_payload in ads:
        status, ad = await add_ad_to_filter(session, filter_id=flt.id, ad_payload=ad_payload)

        if status == "new":
            new_ads_count += 1
            msg = (
                f"✨ Новое объявление!\n\n"
                f"Название: {ad.title}\n"
                f"Город: {ad.city or 'Неизвестно'}\n"
                f"Цена: {ad.last_price or '—'}\n"
                f"🔗 {ad.url}"
            )
            await send_safe(bot, flt.user_id, msg)

        elif status == "price_drop":
            new_ads_count += 1
            msg = (
                f"⬇️ Цена упала!\n\n"
                f"Название: {ad.title}\n"
                f"Город: {ad.city or 'Неизвестно'}\n"
                f"Новая цена: {ad.last_price or '—'}\n"
                f"🔗 {ad.url}"
            )
            await send_safe(bot, flt.user_id, msg)

    await update_last_page(session, flt.id, next_page)
    await session.commit()

    if send_empty and new_ads_count == 0:
        await send_safe(bot, flt.user_id, f"ℹ️ По фильтру «{flt.model}» новых объявлений нет.")


async def process_filters(bot: Bot):
    """
    Проходит по всем фильтрам из БД и обрабатывает их (запуск планировщика).
    """
    async with AsyncSessionLocal() as session:
        filters = await get_all_filters(session)
        for flt in filters:
            try:
                await process_single_filter(session, bot, flt, pages_per_run=3, send_empty=True)
            except Exception:
                logger.exception(f"Ошибка обработки фильтра {flt.id}")

