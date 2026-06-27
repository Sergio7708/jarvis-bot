"""
FSM-заказ — пошаговый диалог оформления заказа с корзиной
"""
from aiogram import Router, types, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from states import OrderFSM, CartFSM
from buttons import html_escape, BTN_CANCEL, BTN_ORDER
from db import (
    get_categories, get_products, get_product, create_order,
    add_to_cart, get_cart, remove_from_cart, clear_cart, cart_total,
    get_product_avg_rating
)
from keyboards import (
    catalog_categories, product_card, main_menu,
    material_kb, color_kb, cart_actions, confirm_order_kb, cancel_kb
)

router = Router()


# ========================
# НАЧАЛО ЗАКАЗА
# ========================

@router.message(F.text == BTN_ORDER)
async def start_order_handler(message: Message):
    """Начать оформление заказа"""
    categories = get_categories()
    if not categories:
        await message.answer("Каталог пуст. Заказ временно недоступен.", reply_markup=main_menu())
        return

    await message.answer(
        "<b>Оформление заказа</b>\n\n"
        "Выберите модель из каталога, чтобы добавить её в корзину. "
        "Можно добавить несколько товаров в один заказ.",
        reply_markup=catalog_categories(categories), parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("order_"))
async def add_to_cart_handler(callback: CallbackQuery, state: FSMContext):
    """Добавить товар в корзину и начать FSM"""
    prod_id = int(callback.data.split("_")[1])
    product = get_product(prod_id)

    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return

    await state.update_data(product_id=prod_id, product_title=product["title"],
                            product_price=product["price"])
    await state.set_state(OrderFSM.enter_material)

    await callback.message.answer(
        f"<b>{html_escape(product['title'])}</b>\n\n"
        f"Шаг 1 — Выберите <b>материал</b> для печати:",
        reply_markup=material_kb(), parse_mode="HTML"
    )
    await callback.answer()


# --- Материал ---
@router.callback_query(OrderFSM.enter_material, F.data.startswith("mat_"))
async def choose_material(callback: CallbackQuery, state: FSMContext):
    mat = callback.data.split("_")[1]
    mat_names = {
        "pla": "PLA", "petg": "PETG", "abs": "ABS",
        "sla": "SLA (смола)", "tpu": "Flex/TPU", "other": "Другой"
    }
    await state.update_data(material=mat_names.get(mat, mat))
    await state.set_state(OrderFSM.enter_color)

    await callback.message.edit_text(
        f"Материал: <b>{mat_names.get(mat, mat)}</b>\n\n"
        f"Шаг 2 — Выберите <b>цвет</b>:",
        reply_markup=color_kb(), parse_mode="HTML"
    )
    await callback.answer()


# --- Цвет ---
@router.callback_query(OrderFSM.enter_color, F.data.startswith("color_"))
async def choose_color(callback: CallbackQuery, state: FSMContext):
    color = callback.data.split("_")[1]
    color_names = {
        "white": "Белый", "black": "Чёрный", "red": "Красный",
        "blue": "Синий", "green": "Зелёный", "yellow": "Жёлтый",
        "orange": "Оранжевый", "purple": "Фиолетовый", "any": "Любой"
    }
    await state.update_data(color=color_names.get(color, color))
    await state.set_state(OrderFSM.enter_quantity)

    await callback.message.edit_text(
        f"Цвет: <b>{color_names.get(color, color)}</b>\n\n"
        f"Шаг 3 — Введите <b>количество</b> (укажите число):",
        parse_mode="HTML"
    )
    await callback.answer()


# --- Количество ---
@router.message(OrderFSM.enter_quantity)
async def choose_quantity(message: Message, state: FSMContext):
    try:
        qty = int(message.text.strip())
        if qty < 1 or qty > 100:
            await message.answer("Укажите число от 1 до 100.")
            return
    except ValueError:
        await message.answer("Пожалуйста, введите число (например: 1, 2, 3).")
        return

    await state.update_data(quantity=qty)
    data = await state.get_data()

    add_to_cart(
        user_id=message.from_user.id,
        product_id=data["product_id"],
        product_title=data["product_title"],
        price=data.get("product_price", 0),
        material=data.get("material", ""),
        color=data.get("color", ""),
        qty=qty
    )

    cart = get_cart(message.from_user.id)
    total = cart_total(message.from_user.id)
    cart_text = format_cart(cart, total)

    await message.answer(
        f"Товар добавлен в корзину!\n\n"
        f"{cart_text}\n\n"
        f"Что дальше?",
        reply_markup=cart_actions(),
        parse_mode="HTML"
    )
    await state.clear()


def format_cart(cart, total):
    """Форматировать содержимое корзины"""
    if not cart:
        return "Корзина пуста"
    text = "<b>Ваша корзина:</b>\n"
    for item in cart:
        price = f"{item['price']}₽" if item['price'] else ""
        text += f"\n• {html_escape(item['title'])}"
        if item['material']:
            text += f" ({html_escape(item['material'])})"
        if item['color']:
            text += f" {html_escape(item['color'])}"
        text += f" x{item['qty']}"
        if price:
            text += f" — {price}/шт"
    text += f"\n\n<b>Итого: {total}₽</b>"
    return text


# ========================
# УПРАВЛЕНИЕ КОРЗИНОЙ
# ========================

@router.callback_query(F.data == "cart_checkout")
async def cart_checkout(callback: CallbackQuery, state: FSMContext):
    """Оформить заказ из корзины"""
    user_id = callback.from_user.id
    cart = get_cart(user_id)

    if not cart:
        await callback.answer("Корзина пуста", show_alert=True)
        return

    await state.set_state(OrderFSM.enter_contact)
    await callback.message.edit_text(
        "<b>Оформление заказа</b>\n\n"
        f"{format_cart(cart, cart_total(user_id))}\n\n"
        f"Шаг 4 — Укажите <b>контакт</b> для связи\n"
        f"(Telegram @username или номер телефона):",
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "cart_clear")
async def cart_clear_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    clear_cart(user_id)
    await callback.message.edit_text("Корзина очищена.")
    await callback.message.answer("Главное меню:", reply_markup=main_menu())
    await callback.answer()


@router.callback_query(F.data == "cart_add")
async def cart_add_more(callback: CallbackQuery):
    categories = get_categories()
    await callback.message.edit_text(
        "Выберите ещё товар для добавления в корзину:",
        reply_markup=catalog_categories(categories)
    )
    await callback.answer()


# ========================
# КОНТАКТ И КОММЕНТАРИЙ
# ========================

@router.message(OrderFSM.enter_contact)
async def choose_contact(message: Message, state: FSMContext):
    contact = message.text.strip()
    if message.contact:
        contact = f"+{message.contact.phone_number}"

    if not contact or len(contact) < 3:
        await message.answer("Укажите корректный контакт.")
        return

    await state.update_data(contact=contact)
    await state.set_state(OrderFSM.enter_comment)

    await message.answer(
        f"Контакт: <b>{html_escape(contact)}</b>\n\n"
        f"Шаг 5 — <b>Комментарий</b> к заказу (или отправьте «-» если без коммента):",
        reply_markup=cancel_kb(), parse_mode="HTML"
    )


@router.message(OrderFSM.enter_comment)
async def choose_comment(message: Message, state: FSMContext):
    if message.text == BTN_CANCEL:
        await state.clear()
        await message.answer("Заказ отменён.", reply_markup=main_menu())
        return

    comment = "" if message.text.strip() in ("-", "") else message.text.strip()
    await state.update_data(comment=comment)
    data = await state.get_data()

    user_id = message.from_user.id
    cart = get_cart(user_id)
    total = cart_total(user_id)

    text = "<b>Проверьте заказ:</b>\n\n"
    for item in cart:
        price_str = f" — {item['price']}₽" if item['price'] else ""
        text += f"<b>{html_escape(item['title'])}</b>{price_str}\n"
        if item['material']:
            text += f"   {html_escape(item['material'])}"
        if item['color']:
            text += f" · {html_escape(item['color'])}"
        text += f" · x{item['qty']}\n"
    text += f"\n<b>Итого: {total}₽</b>"
    text += f"\nКонтакт: <b>{html_escape(data.get('contact', '-'))}</b>"
    if comment:
        text += f"\nКомментарий: {html_escape(comment)}"

    text += "\n\nПодтверждаете заказ?"

    await state.set_state(OrderFSM.confirm)
    await message.answer(text, reply_markup=confirm_order_kb(), parse_mode="HTML")


# ========================
# ПОДТВЕРЖДЕНИЕ
# ========================

@router.callback_query(OrderFSM.confirm, F.data == "confirm_order")
async def confirm_order(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user = callback.from_user
    user_id = user.id
    cart = get_cart(user_id)
    total = cart_total(user_id)

    if not cart:
        await callback.answer("Корзина пуста", show_alert=True)
        return

    items_str = ", ".join([f"{i['title']} x{i['qty']}" for i in cart])
    order_id = create_order(
        user_id=user_id,
        username=user.username or user.full_name,
        product_title=items_str,
        material=", ".join(set(i["material"] for i in cart if i["material"])),
        color=", ".join(set(i["color"] for i in cart if i["color"])),
        qty=sum(i["qty"] for i in cart),
        contact=data.get("contact", ""),
        comment=data.get("comment", ""),
        total_price=total
    )

    from db import add_order_item
    for item in cart:
        add_order_item(order_id, item.get("product_id"), item["title"],
                       item["material"], item["color"], item["qty"], item["price"])

    clear_cart(user_id)

    await callback.message.edit_text(
        f"<b>Заказ #{order_id} оформлен!</b>\n\n"
        f"Скоро мы свяжемся с вами для уточнения деталей.\n\n"
        f"Мои заказы: /myorders",
        parse_mode="HTML"
    )

    if total > 0:
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
        pay_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"Оплатить {total}₽", callback_data=f"pay_order_{order_id}")],
        ])
        await callback.message.answer(
            f"Хотите оплатить заказ #{order_id} онлайн?",
            reply_markup=pay_kb
        )

    await callback.message.answer("Главное меню:", reply_markup=main_menu())
    await state.clear()
    await callback.answer()


@router.callback_query(OrderFSM.confirm, F.data == "edit_order")
async def edit_order_handler(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    cart = get_cart(user_id)
    total = cart_total(user_id)

    await callback.message.edit_text(
        f"{format_cart(cart, total)}\n\n"
        "Вы можете очистить корзину и начать заново:",
        reply_markup=cart_actions(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(OrderFSM.confirm, F.data == "cancel_order")
async def cancel_order_handler(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    clear_cart(user_id)
    await state.clear()
    await callback.message.edit_text("Заказ отменён.")
    await callback.message.answer("Главное меню:", reply_markup=main_menu())
    await callback.answer()


# ========================
# ОТМЕНА В ЛЮБОЙ МОМЕНТ
# ========================

@router.message(StateFilter("*"), F.text == BTN_CANCEL)
async def cancel_any(message: Message, state: FSMContext):
    current = await state.get_state()
    if current is None:
        return
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=main_menu())
