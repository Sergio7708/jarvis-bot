"""
Конфигурация бота @Jarvisvetogorbot
"""
import os
import warnings

# ВАЖНО: Токен был скомпрометирован (попал в публичный репозиторий).
# 1. Зайди в @BotFather → /revoke → выбери бота
# 2. Получи новый токен
# 3. Установи переменную окружения JARVIS_BOT_TOKEN
#    (или создай файл .env с содержимым: JARVIS_BOT_TOKEN=новый_токен)
BOT_TOKEN = os.getenv("JARVIS_BOT_TOKEN")
if not BOT_TOKEN:
    BOT_TOKEN = "7092374074:AAG4X-AyT0Uxjhv-qhSS4vDURTxPo56-sRo"
    warnings.warn(
        "Используется старый (скомпрометированный) токен из config.py! "
        "Смени токен в @BotFather и установи JARVIS_BOT_TOKEN в переменных окружения.",
        RuntimeWarning,
    )

# ID администратора (Сергей)
ADMIN_ID = 483610970

# Каналы
CHANNEL_D3DESIGN = -1003262887157       # @D3ModelerDesigner — канал с моделями
CHANNEL_STL_SOURCE = -1001846902031     # @stlmodelforprint — источник репоста
CHANNEL_3D_COMMUNITY = -1003152125505   # @Modelist_Konstruktor_3D — сообщество
CHANNEL_TEXNICHKA = None                # @texnichka1 — пока не добавлен

# Linked discussion group (если есть)
DISCUSSION_GROUP = None

# Admin list (можно добавить нескольких)
ADMIN_IDS = [ADMIN_ID]

# Путь к БД
DB_PATH = os.path.join(os.path.dirname(__file__), "bot_data.db")

# Настройки репостера
REPOSTER_INTERVAL = 300  # секунд между проверками
REPOSTER_ENABLED = True

# ЮKassa (заполнить своими данными)
YOOKASSA_SHOP_ID = ""
YOOKASSA_SECRET_KEY = ""

# Настройки бота
BOT_NAME = "ВЕКТОР"
STUDIO_NAME = "3Д Моделист Конструктор"
