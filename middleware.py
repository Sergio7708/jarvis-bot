"""
Middleware: бан-лист — блокировка забаненных пользователей
"""
import logging
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from db import is_banned

logger = logging.getLogger(__name__)


class BanMiddleware(BaseMiddleware):
    """Проверяет, не забанен ли пользователь"""

    async def __call__(self, handler, event, data):
        user_id = None

        if isinstance(event, (Message, CallbackQuery)):
            user_id = event.from_user.id

        if user_id and is_banned(user_id):
            logger.info(f"Blocked banned user: {user_id}")
            # Не отвечаем забаненным — они просто не получают ответа
            return

        return await handler(event, data)
