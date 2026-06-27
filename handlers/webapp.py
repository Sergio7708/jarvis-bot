"""
Роутер для Telegram Mini App (WebApp) магазина 3D-печати

Обрабатывает:
- /shop — открыть магазин
- F.web_app_data — получение заказа из Mini App
"""
import json
import logging

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import Message, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import ADMIN_IDS, STUDIO_NAME
from db import create_order, add_order_item
from buttons import html_escape

logger = logging.getLogger(__name__)

router = Router()

# URL Mini App — для продакшена заменить на HTTPS URL
WEBAPP_URL = "https://sergio7708.github.io/jarvis-bot-store/mini_app.html"


@router.message(Command("shop"))
async def cmd_shop(message: Message):
    """Открыть Telegram Mini App магазин"""
    user = message.from_user
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Открыть магазин 3D-печати",
        web_app=WebAppInfo(url=WEBAPP_URL)
    )

    welcome_text = (
        f"<b>3D Каталог</b>\n\n"
        f"Добро пожаловать в студию <b>{STUDIO_NAME}</b>.\n"
        f"Здесь можно быстро выбрать модель, добавить её в корзину и оформить заказ прямо в Telegram.\n\n"
        f"• Каталог моделей\n"
        f"• Избранное и корзина\n"
        f"• Быстрое оформление заказа\n\n"
        f"Нажмите кнопку ниже, чтобы открыть магазин:"
    )
    await message.answer(
        welcome_text,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )


@router.message(F.web_app_data)
async def handle_webapp_data(message: Message):
    """Обработка данных из Mini App (заказ)"""
    user = message.from_user
    web_data = message.web_app_data

    if not web_data or not web_data.data:
        await message.answer("Ошибка: пустые данные от магазина")
        return

    try:
        data = json.loads(web_data.data)
    except json.JSONDecodeError:
        await message.answer("Ошибка: неверный формат данных")
        return

    # Проверяем тип данных
    data_type = data.get("type", "")
    if not data_type and isinstance(data.get("items"), list):
        data_type = "order"

    if data_type == "order":
        await process_order(message, user, data)
    else:
        await message.answer(f"Неизвестный тип данных: {data_type}")


async def process_order(message: Message, user, data: dict):
    """Обработать заказ из Mini App"""
    name = data.get("name", "").strip()
    contact = data.get("contact", "").strip() or data.get("phone", "").strip()
    material = data.get("material", "Не указан")
    color = data.get("color", "Не указан")
    comment = data.get("comment", "")
    delivery = data.get("delivery", "Telegram")
    items = data.get("items", [])
    if not isinstance(items, list):
        items = []
    total = data.get("total", 0)

    if not name:
        await message.answer("Пожалуйста, укажите имя")
        return
    if not contact:
        await message.answer("Пожалуйста, укажите контакт")
        return
    if not items:
        await message.answer("Корзина пуста")
        return

    # Собираем описание заказа для create_order()
    product_titles = [f"{i['title']} x{i['qty']}" for i in items]
    items_text = ", ".join(product_titles)

    # Создаём заказ в БД
    order_id = create_order(
        user_id=user.id,
        username=user.username or user.full_name or name,
        product_title=items_text,
        material=material,
        color=color,
        qty=sum(i.get("qty", 1) for i in items),
        contact=contact,
        comment=f"Связь: {delivery}. {comment}".strip(),
        total_price=total
    )

    # Сохраняем отдельные позиции заказа
    for item in items:
        add_order_item(
            order_id=order_id,
            product_id=item.get("id"),
            product_title=item["title"],
            material=material,
            color=color,
            qty=item.get("qty", 1),
            price=item.get("price", 0)
        )

    logger.info(f"Новый заказ #{order_id} от {name} (@{user.username or '—'}) на сумму {total}₽")

    # Подтверждение пользователю
    confirm_text = (
        f"<b>Заказ #{order_id} принят!</b>\n\n"
    )
    for item in items:
        confirm_text += (
            f"  * {html_escape(item['title'])}"
            f" x{item['qty']} — {item['price'] * item['qty']} ₽\n"
        )
    confirm_text += (
        f"\n<b>Материал:</b> {html_escape(material)}\n"
        f"\n<b>Итого:</b> {total} ₽\n\n"
        f"Ваш заказ передан в обработку. "
        f"Администратор свяжется с вами в ближайшее время."
    )
    try:
        await message.answer(confirm_text, parse_mode="HTML")
    except Exception as e:
        logger.warning(f"Ошибка отправки подтверждения пользователю: {e}")
        await message.answer(
            f"Заказ #{order_id} принят! С вами свяжутся.",
            parse_mode="HTML"
        )

    # Уведомление админам
    admin_text = (
        f"<b>НОВЫЙ ЗАКАЗ #{order_id}</b>\n\n"
        f"<b>Клиент:</b> {html_escape(name)}\n"
        f"<b>Контакт:</b> {html_escape(contact)}\n"
        f"<b>User ID:</b> <code>{user.id}</code>\n"
        f"<b>Username:</b> @{user.username or '—'}\n"
    )
    for item in items:
        admin_text += (
            f"  * {html_escape(item['title'])}"
            f" x{item['qty']} — {item['price'] * item['qty']} ₽\n"
        )
    admin_text += (
        f"\n<b>Материал:</b> {html_escape(material)}\n"
        f"<b>Цвет:</b> {html_escape(color)}\n"
        f"<b>Комментарий:</b> {html_escape(comment) or '—'}\n"
        f"<b>Связь:</b> {html_escape(delivery)}\n"
        f"\n<b>Итого:</b> {total} ₽\n"
        f"{__import__('datetime').datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )

    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(
                admin_id,
                admin_text,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Не удалось уведомить админа {admin_id}: {e}")
