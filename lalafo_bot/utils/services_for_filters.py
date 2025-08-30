from datetime import datetime
from typing import Optional, List, Tuple, Dict, Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Filter, Ad, FilterAd
from .services_for_announcement import add_or_update_ad
import logging
logger = logging.getLogger(__name__)



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
    Обновить last_page у фильтра и залогировать изменение.
    """
    flt = await session.get(Filter, filter_id)
    if not flt:
        logger.warning(f"[DB] Фильтр {filter_id} не найден при обновлении last_page")
        return

    old_page = flt.last_page
    flt.last_page = page
    await session.commit()
    await session.refresh(flt)

    logger.info(f"[DB] Фильтр {filter_id}: last_page {old_page} → {flt.last_page}")


async def get_all_filters(session: AsyncSession) -> List[Filter]:
    """
    Получить все фильтры всех пользователей.
    Используется фоновым планировщиком для обхода.
    """
    res = await session.execute(select(Filter))
    return res.scalars().all()



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

    res = await session.execute(
        select(FilterAd).where(
            FilterAd.filter_id == filter_id,
            FilterAd.ad_id == ad.id
        )
    )
    f_ad = res.scalars().first()

    if f_ad is None:
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

