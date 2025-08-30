# utils/tasks_single.py
import os
import asyncio
import logging
from aiogram import Bot
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from utils.celery_app import celery_app
from utils.services_for_filters import get_filter_by_id
from utils.check_ads import process_single_filter

logger = logging.getLogger(__name__)
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")


async def _run_single_filter_async(filter_id: int, pages_per_run: int):
    engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    bot = Bot(token=BOT_TOKEN)

    try:
        async with SessionLocal() as session:
            flt = await get_filter_by_id(session, filter_id)
            if not flt:
                logger.warning(f"Фильтр с id={filter_id} не найден")
                return

            logger.debug(f"Начата обработка фильтра ID={flt.id}")
            await process_single_filter(
                session, bot, flt,
                pages_per_run=pages_per_run,
                send_empty=False
            )
        await engine.dispose()
    finally:
        await bot.session.close()


@celery_app.task(name="utils.tasks_single.run_single_filter", ignore_result=True)
def run_single_filter(filter_id: int, pages_per_run: int = 3):
    logger.info(f"Celery-таск run_single_filter запущен (filter_id={filter_id})")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_run_single_filter_async(filter_id, pages_per_run))
    finally:
        try:
            loop.run_until_complete(asyncio.sleep(0))
        except Exception:
            pass
        loop.close()
    logger.info(f"Celery-таск run_single_filter завершён (filter_id={filter_id})")

