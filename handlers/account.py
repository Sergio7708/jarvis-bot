"""
Хэндлер для управления аккаунтом: избранное, отзывы, просмотр и отмена заказов
"""
import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from states import ReviewFSM
from db import (
    get_favorites, toggle_favorite, add_review, get_orders_for_user, get_order, update_order_status,
    get_product
)
from keyboards import (
    product_list, product_card, main_menu, cancel_kb,
    review_stars
)
from buttons import html_escape, BTN_CANCEL

logger = logging.getLogger(__name__)
router = Router()


# ========================
# ИЗБРАННОЕ
# ========================

@router.callback_query(F.data.startswith("fav_"))
async def toggle_fav(callback: CallbackQuery):
    user_id = callback.from_user.id
    parts = callback.data.split("_")
    if len(parts) < 2:
        await callback.answer("Ошибка", show_alert=True)
        return
    product_id = int(parts[1])
    toggle_favorite(user_id, product_id)
    product = get_product(product_id)
    if product and callback.message:
        text = (
            f"<b>{html_escape(product['title'])}</b>\n\n"
            f"{html_escape(product['desc'][:200]) if product['desc'] else ''}\n"
            f"<b>Цена:</b> {product['price']}₽\n\n"
            f"Товар {'добавлен в' if is_favorite(user_id, product_id) else 'удалён из'} избранное."
        )
        await callback.message.edit_text(
            text,
            reply_markup=product_card(product['id'], user_id=user_id),
            parse_mode="HTML"
        )
        await callback.answer()


# Вспомогательная (импортируется из db)
from db import is_favorite


@router.callback_query(F.data == "my_favorites")
async def show_favorites(callback: CallbackQuery):
    user_id = callback.from_user.id
    favs = get_favorites(user_id)
    if not favs:
        await callback.message.edit_text("Избранное пусто.\n\nДобавляйте товары в избранное через каталог.")
        await callback.answer()
        return

    text = f"<b>Избранное ({len(favs)}):</b>\n\n"
    for p in favs[:10]:
        text += f"• #{p['id']} {html_escape(p['title'])} — {p['price']}₽\n"
    await callback.message.edit_text(
        text + "\nНажмите на товар, чтобы посмотреть детали.",
        reply_markup=product_list(user_id, favs, back_cb="back_to_catalog"),
        parse_mode="HTML"
    )
    await callback.answer()


# ========================
# ОТЗЫВЫ
# ========================

@router.callback_query(F.data.startswith("review_"))
async def start_review(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    if len(parts) < 2:
        await callback.answer("Ошибка", show_alert=True)
        return
    product_id = int(parts[1])
    product = get_product(product_id)
    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return
    await state.update_data(product_id=product_id)
    await state.set_state(ReviewFSM.enter_rating)
    await callback.message.edit_text(
        f"Оцените товар <b>{html_escape(product['title'])}</b> (1–5):",
        reply_markup=review_stars(product_id),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(ReviewFSM.enter_rating, F.data.startswith("star_"))
async def review_rating(callback: CallbackQuery, state: FSMContext):
    rating = int(callback.data.split("_")[1])
    await state.update_data(rating=rating)
    await state.set_state(ReviewFSM.enter_text)
    stars_str = "\u2605" * rating  # ★×rating
    await callback.message.edit_text(
        f'Оценка: {stars_str}/{rating}/5\n\nНапишите комментарий к отзыву (или отправьте "-"):',
        reply_markup=cancel_kb()
    )
    await callback.answer()


@router.message(ReviewFSM.enter_text)
async def review_text(message: Message, state: FSMContext):
    if message.text == BTN_CANCEL:
        await state.clear()
        uid = message.from_user.id
        await message.answer("Отменено.", reply_markup=main_menu(user_id=uid))
        return
    data = await state.get_data()
    add_review(
        product_id=data["product_id"],
        user_id=message.from_user.id,
        username=message.from_user.full_name or message.from_user.username or "Пользователь",
        rating=data["rating"],
        text=None if message.text.strip() == "-" else message.text.strip()
    )
    await message.answer("Спасибо, ваш отзыв сохранён!", reply_markup=main_menu(user_id=message.from_user.id))
    await state.clear()


# ========================
# ЗАКАЗЫ ПОЛЬЗОВАТЕЛЯ
# ========================

@router.callback_query(F.data == "my_orders")
async def show_my_orders(callback: CallbackQuery):
    user_id = callback.from_user.id
    orders = get_orders_for_user(user_id)
    if not orders:
        await callback.message.edit_text("У вас пока нет заказов.")
        await callback.answer()
        return

    status_names = {
        "new": "Новый", "accepted": "Принят", "working": "В работе",
        "printing": "В печати", "shipped": "Отгружен", "completed": "Выполнен", "cancelled": "Отменён"
    }
    text = "<b>Мои заказы:</b>\n\n"
    for o in orders[:10]:
        s = status_names.get(o["status"], o["status"])
        text += f"#{o['id']} {html_escape(o['product'])} — {s} — {o['date'][:10]}\n"
    await callback.message.edit_text(text, parse_mode="HTML")

    await callback.answer()


@router.callback_query(F.data.startswith("cancel_order_"))
async def cancel_order(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[2])
    order = get_order(order_id)
    if order and order["user_id"] == callback.from_user.id and order["status"] == "new":
        update_order_status(order_id, "cancelled")
        await callback.message.edit_text(f"Заказ #{order_id} отменён.")
    else:
        await callback.answer("Не удалось отменить заказ.", show_alert=True)
    await callback.answer()
