# utils/tasks.py
import os
import asyncio
import logging
from aiogram import Bot
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from utils.celery_app import celery_app
from utils.services_for_filters import get_all_filters
from utils.check_ads import process_single_filter

logger = logging.getLogger(__name__)
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")


async def _run_all_filters_once(*, pages_per_run: int = 3, send_empty: bool = True):
    engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    bot = Bot(token=BOT_TOKEN)

    try:
        async with SessionLocal() as session:
            filters = await get_all_filters(session)
            logger.info(f"Начата обработка всех фильтров (всего: {len(filters)})")

            for flt in filters:
                logger.debug(f"Обработка фильтра ID={flt.id}")
                await process_single_filter(
                    session, bot, flt,
                    pages_per_run=pages_per_run,
                    send_empty=True
                )
        await engine.dispose()
    finally:
        await bot.session.close()


@celery_app.task(name="utils.tasks.run_process_filters", ignore_result=True)
def run_process_filters():
    """Запуск каждые 15 минут из Celery Beat"""
    logger.info("Celery-таск run_process_filters запущен")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_run_all_filters_once(pages_per_run=3, send_empty=True))
    finally:
        try:
            loop.run_until_complete(asyncio.sleep(0))
        except Exception:
            pass
        loop.close()
    logger.info("Celery-таск run_process_filters завершён")

