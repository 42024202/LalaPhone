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
        ad = await create_ad(
            session,
            lalafo_id=lalafo_id,
            title=ad_payload.get("title"),
            city=ad_payload.get("city"),
            url=ad_payload.get("url"),
            price=new_price,
        )
        return "new", ad

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

