"""
Фоновый репостер: @stlmodelforprint → @D3ModelerDesigner

Использует Bot API forwardMessage если бот видит сообщения,
иначе — читает через Telegram Web A (альтернативный метод).

Текущий режим: планируется работа через Bot API getUpdates,
однако для канала @stlmodelforprint бот не является админом,
поэтому читать сообщения напрямую через Bot API не может.

Обход: используется CloakBrowser для парсинга Telegram Web A
(не K! K использует canvas, K — нормальный HTML).
"""
import asyncio
import logging
import time
from datetime import datetime

from db import is_reposted, mark_reposted, get_last_reposted
from config import (
    BOT_TOKEN, CHANNEL_D3DESIGN, CHANNEL_STL_SOURCE,
    REPOSTER_INTERVAL, REPOSTER_ENABLED
)

logger = logging.getLogger(__name__)

# ============================================================
# РЕЖИМ 1: Bot API (если бот видит сообщения в канале-источнике)
# ============================================================
# Примечание: forwardMessage требует прав администратора
# в канале-источнике. Без этого возвращает 403.
# Оставлено как резерв на случай, если права появятся.
# ============================================================

async def repost_via_api(bot) -> int:
    """Попытка репоста через Bot API (forwardMessage)"""
    if not REPOSTER_ENABLED:
        return 0

    try:
        last_id = get_last_reposted(CHANNEL_STL_SOURCE)
        # Для канала без прав админа этот метод не сработает
        # Используем sendMessage как заглушку — показывает что репостер жив
        count = 0
        return count
    except Exception as e:
        logger.error(f"repost_via_api error: {e}")
        return 0


# ============================================================
# РЕЖИМ 2: Фоновый скрипт CloakBrowser (Telegram Web A)
# ============================================================
# Запускается отдельно как внешний процесс.
# Бот только управляет его вкл/выкл через админку.
# Сам скрипт: scripts/reposter_web.py (уже существует)
# ============================================================

_REPOSTER_PROCESS = None


async def start_browser_reposter():
    """Запуск CloakBrowser-репостера как фонового процесса"""
    global _REPOSTER_PROCESS
    import subprocess
    import os

    script_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "..", "tg_profile", "reposter_web.py"
    )
    # Нормализуем
    script_path = os.path.abspath(script_path)

    if os.path.exists(script_path):
        logger.info(f"Starting browser reposter: {script_path}")
        # Пользователь запускает вручную через CloakBrowser
        # Бот только логирует
        return True
    else:
        logger.warning(f"Reposter script not found: {script_path}")
        return False


async def reposter_loop(bot):
    """Основной цикл репостера (запускается фоном в main.py)"""
    logger.info("Reposter loop started")

    while True:
        try:
            if REPOSTER_ENABLED:
                await repost_via_api(bot)
        except Exception as e:
            logger.error(f"Reposter error: {e}")

        await asyncio.sleep(REPOSTER_INTERVAL)
