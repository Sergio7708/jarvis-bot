#!/usr/bin/env python3
"""
Точка входа — бот @Jarvisvetogorbot (ВЕКТОР)
Aiogram 3.x, модульная архитектура

Запуск: python main.py
"""
import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN, BOT_NAME
from db import init_db
from reposter import reposter_loop

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot, dispatcher: Dispatcher):
    """Действия при запуске бота"""
    logger.info(f"Бот @Jarvisvetogorbot ({BOT_NAME}) запускается...")

    # Инициализация БД
    init_db()
    logger.info("База данных инициализирована")

    # Заполняем категории по умолчанию, если таблица пуста
    from db import get_categories, add_category
    if not get_categories():
        logger.info("Добавляем категории по умолчанию...")
        default_cats = [
            ("Игровая техника", ""),
            ("Фигурки", ""),
            ("Оружие", ""),
            ("Детали и запчасти", ""),
            ("Интерьер", ""),
            ("Косплей", ""),
            ("Прочее", ""),
        ]
        for name, emoji in default_cats:
            add_category(name, emoji)
        logger.info(f"Добавлено {len(default_cats)} категорий")

    # Запускаем фоновый репостер
    asyncio.create_task(reposter_loop(bot))
    logger.info("Репостер запущен")

    # Устанавливаем команды
    await bot.set_my_commands([
        {"command": "start", "description": "Главное меню"},
        {"command": "catalog", "description": "Каталог моделей"},
        {"command": "order", "description": "Оформить заказ"},
        {"command": "favorites", "description": "Избранное"},
        {"command": "search", "description": "Поиск по каталогу"},
        {"command": "myorders", "description": "Мои заказы"},
        {"command": "subscribe", "description": "Подписаться на новости"},
        {"command": "unsubscribe", "description": "Отписаться от новостей"},
        {"command": "help", "description": "Помощь"},
        {"command": "status", "description": "Статус бота"},
        {"command": "echo", "description": "Диагностика"},
        {"command": "shop", "description": "Интернет-магазин"},
    ])
    logger.info("Команды установлены")

    logger.info("Бот готов к работе!")


async def on_shutdown(bot: Bot, dispatcher: Dispatcher):
    """Действия при остановке бота"""
    logger.info("Бот останавливается...")


async def main():
    """Главная функция"""
    # Инициализация бота и диспетчера
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    # Middleware: бан-лист
    from middleware import BanMiddleware
    dp.message.middleware(BanMiddleware())
    dp.callback_query.middleware(BanMiddleware())
    logger.info("Middleware бан-листа подключён")

    # Подключаем роутеры
    from handlers.commands import router as commands_router
    from handlers.catalog import router as catalog_router
    from handlers.orders import router as orders_router
    from handlers.admin import router as admin_router
    from handlers.account import router as account_router
    from handlers.payments import router as payments_router
    from handlers.mailing import router as mailing_router
    from handlers.webapp import router as webapp_router
    from handlers.channel_sync import router as channel_sync_router

    dp.include_router(webapp_router)
    dp.include_router(admin_router)
    dp.include_router(account_router)
    dp.include_router(payments_router)
    dp.include_router(mailing_router)
    dp.include_router(channel_sync_router)
    dp.include_router(catalog_router)
    dp.include_router(orders_router)
    dp.include_router(commands_router)

    logger.info(f"Загружено роутеров: 8")

    # Регистрируем коллбеки старта/остановки
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    logger.info("=" * 50)
    logger.info(f"@Jarvisvetogorbot ({BOT_NAME})")
    logger.info("=" * 50)

    # Сброс вебхука перед polling (как в шпаргалке)
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Webhook сброшен, pending updates удалены")

    # Запуск long polling со всеми типами обновлений
    await dp.start_polling(
        bot,
        allowed_updates=dp.resolve_used_update_types()
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.exception(f"Критическая ошибка: {e}")
        sys.exit(1)
