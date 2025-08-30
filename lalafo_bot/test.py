"""Celery app"""
from celery import Celery
from celery.schedules import crontab

celery_app = Celery(
    "lalafo_bot",
    broker="redis://redis:6379/0",
    backend="redis://redis:6379/0",
)

celery_app.conf.update(
    timezone="Asia/Bishkek",
    enable_utc=True,
)

celery_app.conf.beat_schedule = {
    "check-ads-every-15-min": {
        "task": "utils.tasks.run_process_filters",
        "schedule": crontab(minute="*/15"),
    },
}


"""CHECK ADS"""
import asyncio
import logging
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession
from database.session import AsyncSessionLocal
from utils.services_for_filters import add_ad_to_filter, update_last_page, get_all_filters
from parser.model_to_param import MODEL_TO_PARAM
from parser.lalafo_parser import get_filtered_items

logger = logging.getLogger(__name__)


async def process_single_filter(session: AsyncSession, bot: Bot, flt, pages_per_run: int):
    """
    Обрабатывает один фильтр: проходит N страниц, сохраняет объявления и отправляет новые пользователю.
    """
    model_param = MODEL_TO_PARAM.get(flt.model)
    if not model_param:
        return

    page = flt.last_page or 1
    pages_checked = 0

    while pages_checked < pages_per_run:
        ads = await get_filtered_items(model_param, page=page, max_price=flt.max_price)

        if not ads:
            await update_last_page(session, flt.id, 1)
            break

        for ad_payload in ads:
            status, ad = await add_ad_to_filter(session, filter_id=flt.id, ad_payload=ad_payload)

            if status in ("new", "price_drop"):
                msg = (
                    f"📱 {ad.title}\n"
                    f"🏙 {ad.city or 'Неизвестно'}\n"
                    f"💰 {ad.last_price or '—'}\n"
                    f"🔗 {ad.url}"
                )
                try:
                    await bot.send_message(chat_id=flt.user_id, text=msg)
                except Exception as e:
                    logger.error(f"Ошибка при отправке сообщения {flt.user_id}: {e}")

        page += 1
        pages_checked += 1

    await update_last_page(session, flt.id, page)


async def process_filters(bot: Bot):
    async with AsyncSessionLocal() as session:
        filters = await get_all_filters(session)
        for flt in filters:
            try:
                await process_single_filter(session, bot, flt, pages_per_run=3)
            except Exception:
                logger.exception(f"Ошибка обработки фильтра {flt.id}")

"""HANDLERS"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from database.session import AsyncSessionLocal
from utils.services_for_filters import create_filter, get_user_filters, delete_filter
from parser.model_to_param import MODEL_TO_PARAM

from utils.check_ads import process_single_filter as run_single_filter

router = Router()


class FilterCreation(StatesGroup):
    waiting_for_model = State()
    waiting_for_price = State()


@router.message(F.text == "/add_filter")
async def cmd_add_filter(message: Message, state: FSMContext):
    """
    Начало создания фильтра – показываем список моделей.
    """
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=model, callback_data=f"model:{model}")]
            for model in MODEL_TO_PARAM.keys()
        ]
    )
    await message.answer("Выберите модель:", reply_markup=kb)
    await state.set_state(FilterCreation.waiting_for_model)


@router.callback_query(FilterCreation.waiting_for_model, F.data.startswith("model:"))
async def process_model_callback(callback: CallbackQuery, state: FSMContext):
    """
    Пользователь выбрал модель – сохраняем во временное состояние.
    """
    model = callback.data.split(":", 1)[1]
    await state.update_data(model=model)
    await callback.message.answer(
        f"✅ Вы выбрали: {model}\nТеперь введите максимальную цену:"
    )
    await state.set_state(FilterCreation.waiting_for_price)


@router.message(FilterCreation.waiting_for_price)
async def process_price(message: Message, state: FSMContext):
    try:
        price = int(message.text)
    except ValueError:
        await message.answer("⚠ Введите число (цену).")
        return

    data = await state.get_data()
    model = data["model"]

    async with AsyncSessionLocal() as session:
        # 1) создаём фильтр в БД
        flt = await create_filter(
            session,
            user_id=message.from_user.id,
            model=model,
            max_price=price,
        )

        # 2) запускаем Celery-задачу на «один прогон» по фильтру
        run_single_filter.delay(flt.id, pages_per_run=3)

    # 3) подтверждение
    await message.answer(f"🎯 Фильтр создан:\nМодель: {model}\nЦена до: {price}")
    await state.clear()


@router.message(F.text == "/my_filters")
async def cmd_my_filters(message: Message):
    """
    Показать все фильтры пользователя.
    """
    async with AsyncSessionLocal() as session:
        filters = await get_user_filters(session, user_id=message.from_user.id)

    if not filters:
        await message.answer("У вас пока нет фильтров. Добавьте через /add_filter")
        return

    for flt in filters:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="❌ Удалить", callback_data=f"del_filter:{flt.id}")]
            ]
        )
        await message.answer(
            f"📌 Фильтр #{flt.id}\n"
            f"Модель: {flt.model}\n"
            f"Цена до: {flt.max_price if flt.max_price else '—'}",
            reply_markup=kb
        )


@router.callback_query(F.data.startswith("del_filter:"))
async def process_delete_filter(callback: CallbackQuery):
    """
    Удалить фильтр по кнопке.
    """
    filter_id = int(callback.data.split(":")[1])

    async with AsyncSessionLocal() as session:
        ok = await delete_filter(session, filter_id)

    if ok:
        await callback.message.edit_text("❌ Фильтр удалён.")
    else:
        await callback.answer("Фильтр не найден или уже удалён.", show_alert=True)


"""SERVICES FOR ANNOUNCEMENT"""
from datetime import datetime
from typing import Optional, Tuple, Literal, Dict, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from database.models import Ad, FilterAd


async def get_ad_by_lalafo_id(session: AsyncSession, lalafo_id: str) -> Optional[Ad]:
    """
    Найти объявление по уникальному lalafo_id.
    Возвращает объект Ad или None.
    """
    res = await session.execute(select(Ad).where(Ad.lalafo_id == str(lalafo_id)))
    return res.scalars().first()


async def create_ad(
    session: AsyncSession,
    *,
    lalafo_id: str,
    title: str,
    city: Optional[str],
    url: str,
    price: Optional[int],
) -> Ad:
    """
    Создать новое объявление.

    Аргументы:
        lalafo_id — id в Lalafo (строка).
        title — название объявления.
        city — город или None.
        url — ссылка на объявление.
        price — текущая цена (может быть None).

    Возвращает: объект Ad (сохранённый).
    """
    ad = Ad(
        lalafo_id=str(lalafo_id),
        title=title,
        city=city,
        url=url,
        last_price=price,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    session.add(ad)
    await session.commit()
    await session.refresh(ad)
    return ad


async def update_ad_price(
    session: AsyncSession,
    *,
    ad: Ad,
    new_price: Optional[int],
) -> Literal["price_drop", "no_change"]:
    """
    Обновить цену объявления.
    
    Если цена уменьшилась — обновляем и возвращаем "price_drop".
    Если изменений нет — возвращаем "no_change".
    """
    if new_price is not None and ad.last_price is not None:
        if new_price < ad.last_price:
            ad.last_price = new_price
            ad.updated_at = datetime.utcnow()
            await session.commit()
            return "price_drop"
    elif new_price is not None and ad.last_price is None:
        ad.last_price = new_price
        ad.updated_at = datetime.utcnow()
        await session.commit()
    return "no_change"


async def add_or_update_ad(
    session: AsyncSession,
    ad_payload: Dict[str, Any],
) -> Tuple[Literal["new", "price_drop", "seen"], Ad]:
    """
    Добавить новое объявление или обновить существующее.

    ad_payload ожидается в формате:
        {
            "lalafo_id": str | int,
            "title": str,
            "city": Optional[str],
            "url": str,
            "new_price": Optional[int],
        }

    Возвращает (статус, объект Ad):
        - "new"        — объявление впервые добавлено в БД,
        - "price_drop" — цена обновлена вниз,
        - "seen"       — объявление уже есть, изменений нет.
    """
    lalafo_id = str(ad_payload["lalafo_id"])
    new_price = ad_payload.get("new_price")

    ad = await get_ad_by_lalafo_id(session, lalafo_id)
    if ad is None:
        # создаём новое объявление
        ad = await create_ad(
            session,
            lalafo_id=lalafo_id,
            title=ad_payload.get("title"),
            city=ad_payload.get("city"),
            url=ad_payload.get("url"),
            price=new_price,
        )
        return "new", ad

    # обновляем цену, если нужно
    status = await update_ad_price(session, ad=ad, new_price=new_price)
    if status == "price_drop":
        return "price_drop", ad

    return "seen", ad


async def delete_ad(session: AsyncSession, ad_id: int) -> bool:
    """
    Удалить объявление по ID. Возвращает True, если удалено.
    """
    ad = await session.get(Ad, ad_id)
    if not ad:
        return False

    await session.delete(ad)
    await session.commit()
    return True


"""Services for filters."""
# services/filters.py
from datetime import datetime
from typing import Optional, List, Tuple, Dict, Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Filter, Ad, FilterAd
from .services_for_announcement import add_or_update_ad


# -------------------- FILTERS --------------------

async def create_filter(
    session: AsyncSession,
    *,
    user_id: int,
    model: str,
    max_price: Optional[int] = None,
) -> Filter:
    """
    Создать новый фильтр для пользователя.
    """
    flt = Filter(
        user_id=user_id,
        model=model,
        max_price=max_price,
        created_at=datetime.utcnow(),
    )
    session.add(flt)
    await session.commit()
    await session.refresh(flt)
    return flt


async def get_user_filters(session: AsyncSession, user_id: int) -> List[Filter]:
    """
    Получить все фильтры пользователя.
    """
    res = await session.execute(
        select(Filter).where(Filter.user_id == user_id)
    )
    return res.scalars().all()


async def get_filter_by_id(session: AsyncSession, filter_id: int) -> Optional[Filter]:
    """
    Найти фильтр по его ID.
    """
    return await session.get(Filter, filter_id)


async def delete_filter(session: AsyncSession, filter_id: int) -> bool:
    """
    Удалить фильтр (и связанные FilterAd).
    """
    flt = await session.get(Filter, filter_id)
    if not flt:
        return False

    await session.delete(flt)
    await session.commit()
    return True


async def update_last_page(session: AsyncSession, filter_id: int, page: int) -> None:
    """
    Обновить last_page у фильтра.
    """
    flt = await session.get(Filter, filter_id)
    if not flt:
        return
    flt.last_page = page
    await session.commit()


async def get_all_filters(session: AsyncSession) -> List[Filter]:
    """
    Получить все фильтры всех пользователей.
    Используется фоновым планировщиком для обхода.
    """
    res = await session.execute(select(Filter))
    return res.scalars().all()



# -------------------- FILTER + ADS --------------------

async def add_ad_to_filter(
    session: AsyncSession,
    *,
    filter_id: int,
    ad_payload: Dict[str, Any],
) -> Tuple[Literal["new", "price_drop", "seen"], Ad]:
    """
    Добавить объявление к фильтру:
    - создаёт или обновляет объявление (через add_or_update_ad),
    - связывает с фильтром через FilterAd.

    Возвращает:
        - "new"        — объявление новое и впервые привязано к фильтру,
        - "price_drop" — цена уменьшилась,
        - "seen"       — уже есть, изменений нет.
    """
    status, ad = await add_or_update_ad(session, ad_payload)

    # проверяем связку filter <-> ad
    res = await session.execute(
        select(FilterAd).where(
            FilterAd.filter_id == filter_id,
            FilterAd.ad_id == ad.id
        )
    )
    f_ad = res.scalars().first()

    if f_ad is None:
        # создаём новую связь
        f_ad = FilterAd(
            filter_id=filter_id,
            ad_id=ad.id,
            seen_price=ad.last_price,
            created_at=datetime.utcnow(),
        )
        session.add(f_ad)
        await session.commit()
        return status, ad
    else:
        # если цена уменьшилась
        if ad.last_price is not None and f_ad.seen_price is not None:
            if ad.last_price < f_ad.seen_price:
                f_ad.seen_price = ad.last_price
                await session.commit()
                return "price_drop", ad

    return status, ad


async def get_ads_for_filter(session: AsyncSession, filter_id: int) -> List[Ad]:
    """
    Получить все объявления, связанные с фильтром.
    """
    res = await session.execute(
        select(Ad).join(FilterAd).where(FilterAd.filter_id == filter_id)
    )
    return res.scalars().all()


"""BOT TASKS"""
# utils/tasks.py
import asyncio
import os
from aiogram import Bot
from utils.celery_app import celery_app
from database.session import AsyncSessionLocal
from utils.services_for_filters import get_all_filters, get_filter_by_id
from utils.check_ads import process_single_filter

BOT_TOKEN = os.getenv("BOT_TOKEN")


@celery_app.task
def run_process_filters():
    """
    Основная Celery-задача: получить все фильтры и отправить отдельные задачи для каждого.
    """
    asyncio.run(_schedule_filters())


async def _schedule_filters():
    async with AsyncSessionLocal() as session:
        filters = await get_all_filters(session)
        for flt in filters:
            # для каждого фильтра создаём отдельную celery-задачу
            run_single_filter.delay(flt.id, 3)


@celery_app.task
def run_single_filter(filter_id: int, pages_per_run: int = 3):
    """
    Celery-задача для обработки одного фильтра.
    """
    asyncio.run(_process_single_filter(filter_id, pages_per_run))


async def _process_single_filter(filter_id: int, pages_per_run: int):
    async with AsyncSessionLocal() as session:
        flt = await get_filter_by_id(session, filter_id)
        if not flt:
            return

        bot = Bot(token=BOT_TOKEN)
        try:
            await process_single_filter(session, bot, flt, pages_per_run=pages_per_run)
        finally:
            await bot.session.close()


