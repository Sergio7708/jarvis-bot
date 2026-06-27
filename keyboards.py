"""
Клавиатуры для бота @Jarvisvetogorbot
"""
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from buttons import *


def main_menu(user_id=None):
    """Главное меню — для админа расширенное"""
    is_admin = user_id == 483610970
    if is_admin:
        kb = [
            [KeyboardButton(text=BTN_CATALOG), KeyboardButton(text=BTN_ORDER)],
            [KeyboardButton(text=BTN_FAVORITES), KeyboardButton(text=BTN_SHOP)],
            [KeyboardButton(text=BTN_ORDERS), KeyboardButton(text=BTN_STATS)],
            [KeyboardButton(text=BTN_ADD_PRODUCT), KeyboardButton(text=BTN_CATEGORIES)],
            [KeyboardButton(text=BTN_MAILING), KeyboardButton(text=BTN_PHOTO)],
            [KeyboardButton(text=BTN_BACKUP), KeyboardButton(text=BTN_BANLIST)],
            [KeyboardButton(text=BTN_ABOUT), KeyboardButton(text=BTN_CONTACTS)],
        ]
    else:
        kb = [
            [KeyboardButton(text=BTN_CATALOG), KeyboardButton(text=BTN_ORDER)],
            [KeyboardButton(text=BTN_FAVORITES), KeyboardButton(text=BTN_SHOP)],
            [KeyboardButton(text=BTN_ABOUT), KeyboardButton(text=BTN_CONTACTS)],
        ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def cancel_kb():
    """Отмена действия"""
    kb = [[KeyboardButton(text=BTN_CANCEL)]]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def contact_kb():
    """Кнопка отправки контакта"""
    kb = [[KeyboardButton(text="Отправить номер", request_contact=True)]]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, one_time_keyboard=True)


# === Inline-клавиатуры ===

def catalog_categories(categories):
    """Список категорий каталога"""
    builder = InlineKeyboardBuilder()
    for cat in categories:
        emoji = cat["emoji"] or ""
        builder.button(text=f"{emoji} {cat['name']}", callback_data=f"cat_{cat['id']}")
    builder.adjust(2)
    return builder.as_markup()


def product_list(products, page=0, total_pages=1):
    """Список товаров в категории"""
    builder = InlineKeyboardBuilder()
    for p in products:
        title = p["title"][:28] + "…" if len(p["title"]) > 28 else p["title"]
        price = f" | {p['price']}₽" if p["price"] else ""
        builder.button(text=f"{title}{price}", callback_data=f"prod_{p['id']}")
    builder.adjust(1)

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="← Назад", callback_data=f"cat_{page-1}_page"))
    nav.append(InlineKeyboardButton(text="← В категории", callback_data="back_cats"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="Вперёд", callback_data=f"cat_{page+1}_page"))

    return InlineKeyboardMarkup(inline_keyboard=[*builder.export(), nav])


def product_card(product_id, in_catalog=True, is_fav=False, user_id=None):
    """Кнопки для карточки товара
    Для админа (483610970) — кнопки редактировать/удалить
    Для покупателя — только «Заказать» + «Назад»
    """
    builder = InlineKeyboardBuilder()
    is_admin = (user_id == 483610970)
    if is_admin:
        builder.button(text="✏️ Редактировать", callback_data=f"edit_{product_id}")
        builder.button(text="🗑 Удалить", callback_data=f"del_{product_id}")
    builder.button(text="Заказать", callback_data=f"order_{product_id}")
    if not is_admin and is_fav:
        builder.button(text="♥", callback_data=f"fav_{product_id}")
    if in_catalog:
        builder.button(text="← Назад", callback_data="back_products")
    if is_admin:
        builder.adjust(2, 1, 1)
    else:
        builder.adjust(1, 1)
    return builder.as_markup()


def order_status_actions(order_id):
    """Кнопки смены статуса заказа (админ)"""
    builder = InlineKeyboardBuilder()
    builder.button(text="Принять", callback_data=f"ostatus_{order_id}_accepted")
    builder.button(text="В работу", callback_data=f"ostatus_{order_id}_working")
    builder.button(text="В печать", callback_data=f"ostatus_{order_id}_printing")
    builder.button(text="Отгружен", callback_data=f"ostatus_{order_id}_shipped")
    builder.button(text="Отменить", callback_data=f"ostatus_{order_id}_cancelled")
    builder.button(text="Фото", callback_data=f"ophoto_{order_id}")
    builder.adjust(2)
    return builder.as_markup()


def material_kb():
    """Выбор материала для печати"""
    builder = InlineKeyboardBuilder()
    builder.button(text="PLA", callback_data="mat_pla")
    builder.button(text="PETG", callback_data="mat_petg")
    builder.button(text="ABS", callback_data="mat_abs")
    builder.button(text="SLA (смола)", callback_data="mat_sla")
    builder.button(text="Flex/TPU", callback_data="mat_tpu")
    builder.button(text="Другой", callback_data="mat_other")
    builder.adjust(2)
    return builder.as_markup()


def color_kb():
    """Выбор цвета"""
    colors = [
        ("Белый", "white"), ("Чёрный", "black"),
        ("Красный", "red"), ("Синий", "blue"),
        ("Зелёный", "green"), ("Жёлтый", "yellow"),
        ("Оранжевый", "orange"), ("Фиолетовый", "purple"),
        ("Любой", "any"),
    ]
    builder = InlineKeyboardBuilder()
    for label, val in colors:
        builder.button(text=label, callback_data=f"color_{val}")
    builder.adjust(2)
    return builder.as_markup()


def confirm_order_kb():
    """Подтверждение заказа"""
    builder = InlineKeyboardBuilder()
    builder.button(text="Подтвердить", callback_data="confirm_order")
    builder.button(text="Изменить", callback_data="edit_order")
    builder.button(text="Отменить", callback_data="cancel_order")
    builder.adjust(1)
    return builder.as_markup()


def admin_order_nav(page, total, status_filter=None):
    """Навигация по заказам (админ) + фильтры"""
    builder = InlineKeyboardBuilder()

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="←", callback_data=f"oadmin_{page-1}"))
    nav.append(InlineKeyboardButton(text=f"{page+1}/{total}", callback_data="noop"))
    if page < total - 1:
        nav.append(InlineKeyboardButton(text="→", callback_data=f"oadmin_{page+1}"))
    if nav:
        builder.row(*nav)

    filters = []
    current = status_filter or 'all'
    for key, label in [('all', 'Все'), ('new', 'Новые'), ('accepted', 'Приняты'), ('working', 'В работе'), ('printing', 'В печати'), ('shipped', 'Отгружены'), ('cancelled', 'Отменены')]:
        if key == current:
            filters.append(InlineKeyboardButton(text=f"•{label}•", callback_data="noop"))
        else:
            filters.append(InlineKeyboardButton(text=label, callback_data=f"ofilter_{key}"))
    builder.row(*filters)

    return builder.as_markup()


def rating_kb():
    """Выбор оценки 1-5"""
    builder = InlineKeyboardBuilder()
    for i in range(1, 6):
        stars = "★" * i
        builder.button(text=stars, callback_data=f"rate_{i}")
    builder.adjust(5)
    return builder.as_markup()


def review_stars(product_id):
    """Inline-клавиатура для оценки товара (1–5 звёзд)"""
    builder = InlineKeyboardBuilder()
    for i in range(1, 6):
        builder.button(text="★" * i, callback_data=f"star_{i}")
    builder.adjust(5)
    return builder.as_markup()


def edit_product_fields():
    """Выбор поля для редактирования товара"""
    builder = InlineKeyboardBuilder()
    builder.button(text="Название", callback_data="edit_title")
    builder.button(text="Описание", callback_data="edit_desc")
    builder.button(text="Цена", callback_data="edit_price")
    builder.button(text="Фото", callback_data="edit_photo")
    builder.button(text="Категория", callback_data="edit_category")
    builder.adjust(2)
    return builder.as_markup()


def mailing_actions():
    """Кнопки для рассылки"""
    builder = InlineKeyboardBuilder()
    builder.button(text="Отправить", callback_data="mail_send")
    builder.button(text="Редактировать", callback_data="mail_edit")
    builder.button(text="Отменить", callback_data="mail_cancel")
    builder.adjust(1)
    return builder.as_markup()


def cart_actions(has_items=True):
    """Кнопки корзины"""
    builder = InlineKeyboardBuilder()
    if has_items:
        builder.button(text="Оформить", callback_data="cart_checkout")
        builder.button(text="Очистить", callback_data="cart_clear")
    builder.button(text="Добавить ещё", callback_data="cart_add")
    builder.adjust(1)
    return builder.as_markup()


def payment_methods():
    """Выбор способа оплаты"""
    builder = InlineKeyboardBuilder()
    builder.button(text="ЮKassa", callback_data="pay_yookassa")
    builder.button(text="Перевод на карту", callback_data="pay_card")
    builder.button(text="Наличные", callback_data="pay_cash")
    builder.adjust(1)
    return builder.as_markup()
