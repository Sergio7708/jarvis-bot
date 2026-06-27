"""
Хэндлер каталога — просмотр категорий, товаров, поиск
"""
from aiogram import Router, types, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from db import get_categories, get_products, get_product, search_products, get_product_avg_rating, get_product_reviews, is_favorite
from buttons import html_escape
from keyboards import catalog_categories, product_list, product_card, main_menu

router = Router()


async def show_catalog(message: Message = None, callback: CallbackQuery = None):
    """Показать категории каталога"""
    categories = get_categories()
    if not categories:
        text = "Каталог пока пуст. Загляните позже!"
        if message:
            await message.answer(text)
        elif callback:
            await callback.message.edit_text(text)
        return

    text = "<b>Категории</b>\n\nВыберите раздел:"
    if message:
        await message.answer(text, reply_markup=catalog_categories(categories), parse_mode="HTML")
    elif callback:
        await callback.message.edit_text(text, reply_markup=catalog_categories(categories), parse_mode="HTML")


@router.message(F.text.in_(["Каталог", "/catalog"]))
async def cmd_catalog(message: Message):
    await show_catalog(message=message)


@router.callback_query(F.data.startswith("cat_"))
async def show_category(callback: CallbackQuery):
    """Показать товары в категории"""
    data = callback.data
    # cat_ID or cat_PAGE_page
    if data.endswith("_page"):
        # Навигация по страницам (если реализовано)
        await callback.answer()
        return

    cat_id = int(data.split("_")[1])
    products = get_products(cat_id)
    cat_name = ""

    categories = get_categories()
    for c in categories:
        if c["id"] == cat_id:
            cat_name = c["name"]
            break

    if not products:
        await callback.message.edit_text(
            f"В разделе «{html_escape(cat_name)}» пока нет товаров.",
            reply_markup=catalog_categories(get_categories()),
            parse_mode="HTML"
        )
        await callback.answer()
        return

    text = f"<b>{html_escape(cat_name)}</b>\n\nВыберите модель:"
    await callback.message.edit_text(
        text,
        reply_markup=product_list(products),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("prod_"))
async def show_product(callback: CallbackQuery):
    """Показать карточку товара"""
    prod_id = int(callback.data.split("_")[1])
    product = get_product(prod_id)

    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return

    title = product["title"]
    desc = product["desc"] or "Описание отсутствует"
    price = f"{product['price']} ₽" if product["price"] else "Цена по запросу"

    # Рейтинг
    rating = get_product_avg_rating(prod_id)
    rating_text = ""
    if rating["count"] > 0:
        stars = "★" * round(rating["avg"])
        rating_text = f"\n\n{stars} {rating['avg']} ({rating['count']} отзывов)"

    # Избранное
    user_id = callback.from_user.id
    fav_status = is_favorite(user_id, prod_id)

    # Кнопка отзыва
    reviews = get_product_reviews(prod_id, limit=3)

    text = (
        f"<b>{html_escape(title)}</b>\n\n"
        f"{html_escape(desc)}\n\n"
        f"<b>Цена:</b> {price}"
        f"{rating_text}"
    )

    kb = product_card(prod_id, is_fav=fav_status, user_id=user_id)

    # Если есть отзывы — добавляем кнопку
    if reviews:
        from aiogram.types import InlineKeyboardButton
        import json
        kb.inline_keyboard.append([
            InlineKeyboardButton(text=f"Отзывы ({rating['count']})", callback_data=f"reviews_{prod_id}")
        ])

    if product["photo"]:
        await callback.message.delete()
        await callback.message.answer_photo(
            photo=product["photo"],
            caption=text,
            reply_markup=kb,
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            text,
            reply_markup=kb,
            parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data.startswith("reviews_"))
async def show_reviews(callback: CallbackQuery):
    """Показать отзывы на товар"""
    prod_id = int(callback.data.split("_")[1])
    product = get_product(prod_id)
    reviews = get_product_reviews(prod_id)
    rating = get_product_avg_rating(prod_id)

    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return

    stars = "★" * round(rating["avg"]) if rating["count"] > 0 else "Нет оценок"
    text = f"<b>Отзывы: {html_escape(product['title'])}</b>\n\n"
    text += f"Рейтинг: {stars} ({rating['avg']}/{rating['count']})\n\n"

    if not reviews:
        text += "Отзывов пока нет.\n\nБудьте первым!"
    else:
        for r in reviews:
            r_stars = "★" * r["rating"]
            r_user = r["username"] or f"Пользователь #{r['user_id']}"
            text += f"{r_stars} — <b>{html_escape(r_user)}</b>\n"
            if r["text"]:
                text += f"  {html_escape(r['text'])}\n"
            text += f"  {r['date'][:10]}\n\n"

    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Оставить отзыв", callback_data=f"review_{prod_id}")],
        [InlineKeyboardButton(text="← К товару", callback_data=f"prod_{prod_id}")],
    ])

    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


# ========================
# ПОИСК
# ========================

@router.message(F.text == "Поиск")
async def cmd_search_prompt(message: Message):
    await message.answer(
        "<b>Поиск по каталогу</b>\n\n"
        "Напишите название модели или ключевое слово для поиска:",
        parse_mode="HTML"
    )


@router.message(Command("search"))
async def cmd_search_command(message: Message):
    query = message.text.replace("/search", "", 1).strip()
    if not query:
        await message.answer(
            "Напишите запрос после команды, например:\n"
            "/search танк\n"
            "/search фигурка",
            parse_mode="HTML"
        )
        return
    await perform_search(message, query)


async def perform_search(message: Message, query: str):
    """Выполнить поиск и показать результаты"""
    results = search_products(query)

    if not results:
        await message.answer(
            f"По запросу «<b>{html_escape(query)}</b>» ничего не найдено.\n\n"
            f"Попробуйте другие ключевые слова или зайдите в каталог.",
            parse_mode="HTML"
        )
        return

    text = f"<b>Результаты поиска: «{html_escape(query)}»</b>\n\n"
    for p in results[:10]:
        price = f"{p['price']}₽" if p['price'] else "Цена по запросу"
        text += f"• <b>{html_escape(p['title'])}</b> — {price}\n"

    text += f"\nНайдено: {len(results)}"

    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    buttons = []
    for p in results[:10]:
        buttons.append([InlineKeyboardButton(text=p["title"][:40], callback_data=f"prod_{p['id']}")])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.message(lambda msg: msg.text and len(msg.text) > 1 and not msg.text.startswith("/"))
async def search_fallback(message: Message, state: FSMContext):
    """Если пользователь ввёл текст — игнорируем FSM-состояния"""
    current_state = await state.get_state()
    if current_state is not None:
        return  # не мешаем FSM-диалогам
    # Поиск срабатывает только если есть совпадения
    if len(message.text) < 3:
        return
    results = search_products(message.text)
    if results and len(results) > 0:
        await perform_search(message, message.text)


@router.callback_query(F.data == "back_cats")
async def back_to_categories(callback: CallbackQuery):
    """Назад к списку категорий"""
    await show_catalog(callback=callback)
    await callback.answer()


@router.callback_query(F.data == "back_products")
async def back_to_products(callback: CallbackQuery):
    """Вернуться к списку продуктов (на категории)"""
    await show_catalog(callback=callback)
    await callback.answer()
