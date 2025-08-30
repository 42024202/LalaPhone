from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from database.session import AsyncSessionLocal
from utils.services_for_filters import create_filter, get_user_filters, delete_filter
from parser.model_to_param import MODEL_TO_PARAM

from utils.tasks_single import run_single_filter

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

