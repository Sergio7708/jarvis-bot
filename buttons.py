"""
Константы текста кнопок — единый источник для keyboards.py и admin.py
"""
BTN_CATALOG = "Каталог"
BTN_ORDER = "Заказать"
BTN_FAVORITES = "Избранное"
BTN_SEARCH = "Поиск"
BTN_ABOUT = "О нас"
BTN_CONTACTS = "Контакты"
BTN_SHOP = "Магазин"

BTN_ORDERS = "Заказы"
BTN_ADD_PRODUCT = "Добавить товар"
BTN_CATEGORIES = "Категории"
BTN_STATS = "Статистика"
BTN_REPOSTER = "Репостер"
BTN_MAILING = "Рассылка"
BTN_PHOTO = "Фотоотчёт"
BTN_BACKUP = "Бэкап"
BTN_BANLIST = "Бан-лист"

BTN_BACK = "← Назад"
BTN_CANCEL = "✕ Отмена"

import unicodedata
import html

def strip_emoji(text):
    """Удалить эмодзи, оставить только текст"""
    return ''.join(c for c in text if unicodedata.category(c) != 'So' and unicodedata.category(c) != 'Sk').strip()

def text_match(button_text):
    """Создаёт фильтр: message.text содержит текстовую часть кнопки (без эмодзи)"""
    keyword = strip_emoji(button_text)
    return lambda msg: msg.text and keyword.lower() in msg.text.lower()

def html_escape(text):
    """Экранировать HTML-символы для безопасного использования в parse_mode='HTML'.
    Заменяет &, <, > на &amp;, &lt;, &gt; соответственно.
    Также заменяет @ на полный @, чтобы Telegram не создавал кликабельные ссылки на группы."""
    if not text:
        return text or ""
    result = html.escape(str(text), quote=False)
    # Заменяем @ на полный @ (U+FF20) — предотвращает авто-ссылки на группы/юзеров
    result = result.replace("@", "\uff20")
    return result
