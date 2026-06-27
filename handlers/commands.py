"""
Хэндлеры команд: /start, /help, /status, текстовое меню
"""
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import Message
from keyboards import main_menu
from db import is_subscribed, subscribe_user

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message):
    user = message.from_user
    text = (
        f"Привет, {user.first_name}!\\n\\n"
        f"Я — <b>ВЕКТОР</b>, бот-помощник студии <b>3Д Моделист Конструктор</b>.\\n\\n"
        f"* <b>Каталог</b> — посмотреть модели\\n"
        f"* <b>Заказать</b> — оформить заказ\\n"
        f"* <b>Избранное</b> — сохранённые модели\\n"
        f"* <b>Поиск</b> — найти модель\\n"
        f"* <b>О нас</b> — информация о студии\\n\\n"
        f"Выбери действие в меню:"
    )
    is_admin = message.from_user.id in [483610970]
    await message.answer(text, reply_markup=main_menu(user_id=message.from_user.id), parse_mode="HTML")

    # Автоподписка на новости
    if not is_subscribed(user.id):
        subscribe_user(user.id, user.username or user.full_name)


@router.message(Command("help"))
async def cmd_help(message: Message):
    text = (
        "<b>Помощь по командам</b>\\n\\n"
        "/start — Главное меню\\n"
        "/catalog — Каталог моделей\\n"
        "/order — Оформить заказ\\n"
        "/favorites — Избранное\\n"
        "/search <текст> — Поиск по каталогу\\n"
        "/myorders — Мои заказы\\n"
        "/subscribe — Подписаться на новости\\n"
        "/unsubscribe — Отписаться от новостей\\n"
        "/status — Статус бота\\n"
        "/help — Эта справка\\n"
        "/shop — Интернет-магазин"
    )

    if message.from_user.id in [483610970]:
        text += (
            "\\n\\n<b>Админ-команды:</b>\\n"
            "/admin — Панель управления\\n"
        )

    await message.answer(text, parse_mode="HTML")


@router.message(Command("status"))
async def cmd_status(message: Message):
    import time
    text = (
        "<b>ВЕКТОР</b> — статус\\n\\n"
        "Бот активен\\n"
        "База данных: работает\\n"
        "Корзина: активна\\n"
        "Репостер: активен\\n"
        "Поиск: активен\\n"
        "Канал @D3ModelerDesigner: подключён\\n\\n"
        f"<code>{time.strftime('%d.%m.%Y %H:%M')}</code>"
    )
    await message.answer(text, parse_mode="HTML")


@router.message(Command("echo"))
async def cmd_echo(message: Message):
    """Диагностика — показать что получил бот"""
    import json
    text = (
        f"<b>Диагностика сообщения</b>\\n\\n"
        f"User: {message.from_user.id}\\n"
        f"Текст: <code>{message.text or '—'}</code>\\n"
        f"Chat: {message.chat.id} ({message.chat.type})\\n"
        f"{__import__('datetime').datetime.now().strftime('%H:%M:%S')}"
    )
    await message.answer(text, parse_mode="HTML")


@router.message()
async def text_handler(message: Message):
    """Обработка текстовых кнопок главного меню"""
    if not message.text:
        return
    text = message.text.strip().lower()

    if text in ("каталог", "/catalog"):
        from handlers.catalog import show_catalog
        await show_catalog(message=message)
    elif text in ("заказать", "/order"):
        from handlers.orders import cmd_order
        await cmd_order(message, None)
    elif text in ("избранное", "/favorites"):
        from handlers.account import show_favorites
        await show_favorites(message)
    elif text in ("поиск", "/search"):
        from handlers.catalog import cmd_search_prompt
        await cmd_search_prompt(message)
    elif text in ("о нас",):
        await about_us(message)
    elif text in ("контакты",):
        await contacts(message)
    elif text in ("магазин", "/shop"):
        from handlers.webapp import cmd_shop
        await cmd_shop(message)
    elif text in ("назад",):
        await cmd_start(message)


async def about_us(message: Message):
    text = (
        "<b>3Д Моделист Конструктор</b>\\n\\n"
        "Студия 3D-печати и 3D-моделирования.\\n\\n"
        "* Печать на заказ (FDM, SLA)\\n"
        "* Создание 3D-моделей\\n"
        "* Игровая техника и фигурки\\n"
        "* Детали и запчасти\\n"
        "* Постобработка, покраска\\n\\n"
        "Доставка по всей РФ"
    )
    await message.answer(text, parse_mode="HTML")


async def contacts(message: Message):
    text = (
        "<b>Контакты</b>\\n\\n"
        "Сергей\\n"
        "Telegram: @SergeyIvanovic\\n"
        "Канал: @D3ModelerDesigner\\n"
        "Сообщество: @Modelist_Konstruktor_3D"
    )
    await message.answer(text, parse_mode="HTML")
