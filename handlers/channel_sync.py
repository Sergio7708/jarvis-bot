"""
Автоимпорт карточек товара из Telegram-каналов в каталог.

Режим работы:
- если бот является участником/админом канала, он ловит channel_post;
- создаёт товар только из постов с фото;
- чистит ссылки, упоминания, STL/OBJ/ZIP-файлы и мусорные сигналы;
- сохраняет реальный photo_file_id, чтобы Mini App показывала настоящую фотокарточку.
"""

from __future__ import annotations

import html
import logging
import re

from aiogram import Router, F
from aiogram.types import Message

from buttons import html_escape
from config import ADMIN_IDS, CHANNEL_3D_COMMUNITY, CHANNEL_D3DESIGN
from db import (
    add_category,
    add_product,
    get_categories,
    get_catalog_import,
    mark_catalog_import,
    update_product,
)

# Import export function
import sys, os, json, sqlite3
EXPORT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "webapp", "products.json")

def _export_products():
    """Export all active products to webapp/products.json."""
    try:
        from db import DB_PATH
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("""
            SELECT p.id, p.title, p.description, p.price, p.photo_file_id, c.name as cat
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE p.is_active = 1
            ORDER BY p.id
        """)
        cols = [d[0] for d in c.description]
        products = []
        for row in c.fetchall():
            d = dict(zip(cols, row))
            products.append({
                "id": d["id"],
                "title": (d.get("title") or "Без названия"),
                "description": (d.get("description") or ""),
                "price": (d.get("price") or 1000),
                "image": (d.get("photo_file_id") or ""),
                "category": (d.get("cat") or "Прочее"),
                "rating": 4.5
            })
        conn.close()
        with open(EXPORT_PATH, "w", encoding="utf-8") as f:
            json.dump(products, f, ensure_ascii=False, indent=2)
        logger.info(f"Exported {len(products)} products to products.json")
    except Exception as e:
        logger.error(f"Export to products.json failed: {e}")

logger = logging.getLogger(__name__)
router = Router()

SOURCE_CHANNELS = {
    CHANNEL_D3DESIGN,
    CHANNEL_3D_COMMUNITY,
}

BANNED_EXTENSIONS = (
    ".stl",
    ".obj",
    ".step",
    ".stp",
    ".fbx",
    ".blend",
    ".3mf",
    ".zip",
    ".rar",
    ".7z",
    ".tar",
    ".gz",
)

LINK_RE = re.compile(r"(?:https?://\S+|t\.me/\S+|@\w+)", re.IGNORECASE)
FILE_RE = re.compile(r"(?:\b\w+\.(?:stl|obj|step|stp|fbx|blend|3mf|zip|rar|7z|tar|gz)\b)", re.IGNORECASE)
PRICE_RE = re.compile(r"(?:цена|price)[:\s]*([0-9][0-9\s]{1,9})(?:\s*(?:₽|руб\.?|рублей|р\.))?", re.IGNORECASE)
MONEY_RE = re.compile(r"([0-9][0-9\s]{1,9})\s*(?:₽|руб\.?|рублей|р\.)", re.IGNORECASE)

KEYWORDS = {
    "Игровая техника": [
        "танк", "бтр", "бронетрансп", "бмп", "вертол", "самол", "корабл",
        "машин", "авто", "техника", "дрон", "экскаватор", "трактор", "робот",
    ],
    "Косплей": [
        "косплей", "шлем", "маска", "helmet", "armor", "броня", "костюм", "prop",
    ],
    "Оружие": [
        "оруж", "бластер", "пистолет", "винтовка", "меч", "сабля", "топор", "нож",
        "rifle", "blaster", "gun",
    ],
    "Детали и запчасти": [
        "детал", "запчаст", "шестер", "крепеж", "кронштейн", "адаптер", "держател",
        "соединител", "bracket", "gear", "mount",
    ],
    "Интерьер": [
        "лампа", "светильник", "ваза", "подставк", "органайзер", "кашпо", "декор",
        "полка", "подсвечник", "table", "stand", "holder",
    ],
    "Фигурки": [
        "фигур", "бюст", "стату", "дракон", "рыцар", "персонаж", "герой", "character",
        "miniature", "model", "figur",
    ],
}

BAD_PHRASES = [
    "подпиш",
    "подписывай",
    "ссылка",
    "t.me/",
    "joinchat",
    "наш канал",
    "другой канал",
    "группа",
    "чат",
    "бот",
    "скачать",
]


def _clean_line(line: str) -> str:
    line = html.unescape(line or "")
    line = LINK_RE.sub("", line)
    line = FILE_RE.sub("", line)
    line = re.sub(r"\s+", " ", line).strip()
    return line


def clean_source_text(text: str) -> str:
    if not text:
        return ""

    lines: list[str] = []
    for raw in text.splitlines():
        line = _clean_line(raw)
        if not line:
            continue
        lowered = line.lower()
        if any(p in lowered for p in BAD_PHRASES):
            continue
        if any(ext in lowered for ext in BANNED_EXTENSIONS):
            continue
        lines.append(line)

    cleaned = "\n".join(lines).strip()
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


def extract_title(cleaned_text: str, fallback: str = "") -> str:
    lines = [line.strip(" •·-|:\t") for line in (cleaned_text or "").splitlines() if line.strip()]
    for line in lines:
        if len(line) < 3:
            continue
        if line.lower() in {"stl", "obj", "zip", "rar", "3d"}:
            continue
        if len(line) > 95:
            return line[:92].rsplit(" ", 1)[0].strip() or line[:92].strip()
        return line
    return fallback.strip() or "Новая модель"


def extract_description(cleaned_text: str, title: str) -> str:
    if not cleaned_text:
        return ""

    lines = [line.strip() for line in cleaned_text.splitlines() if line.strip()]
    if not lines:
        return ""

    # Если первая строка выглядит как название — убираем её из описания.
    desc_lines = lines[:]
    if title and desc_lines and desc_lines[0].startswith(title[:20]):
        desc_lines = desc_lines[1:]

    description = "\n".join(desc_lines).strip()
    if len(description) > 420:
        description = description[:417].rsplit(" ", 1)[0].strip() + "..."
    return description


def extract_price(text: str) -> int:
    if not text:
        return 0

    for regex in (PRICE_RE, MONEY_RE):
        match = regex.search(text)
        if match:
            digits = re.sub(r"\D", "", match.group(1))
            if digits:
                value = int(digits)
                if value >= 50:
                    return value
    return 0


def normalize_category(value: str | None) -> str:
    raw = (value or "").lower()
    if not raw:
        return "Прочее"
    for category, keywords in KEYWORDS.items():
        if any(keyword in raw for keyword in keywords):
            return category
    return "Прочее"


def choose_category(title: str, description: str, channel_title: str = "") -> str:
    combined = f"{title} {description} {channel_title}".lower()
    return normalize_category(combined)


def ensure_category(name: str) -> int:
    categories = get_categories()
    for cat in categories:
        if cat["name"] == name:
            return cat["id"]
    add_category(name)
    categories = get_categories()
    for cat in categories:
        if cat["name"] == name:
            return cat["id"]
    raise RuntimeError(f"Не удалось создать категорию: {name}")


def looks_like_model_post(message: Message) -> bool:
    caption = message.caption or message.text or ""
    lowered = caption.lower()

    if message.document:
        name = (getattr(message.document, "file_name", "") or "").lower()
        if name.endswith(BANNED_EXTENSIONS):
            return False
        if any(ext in name for ext in BANNED_EXTENSIONS):
            return False
        if any(ext in lowered for ext in BANNED_EXTENSIONS):
            return False

    if not message.photo:
        return False

    if not caption.strip():
        return False

    if any(phrase in lowered for phrase in ["stl", ".stl", "obj", ".obj", "zip", ".zip", "rar", ".rar"]):
        # Фото есть, но пост выглядит как файл-объявление — лучше не превращать его в товар.
        return False

    return True


def build_source_url(message: Message) -> str:
    username = getattr(message.chat, "username", None)
    if username:
        return f"https://t.me/{username}/{message.message_id}"
    return ""


def import_catalog_post(message: Message) -> tuple[int, bool] | None:
    """Импортировать один канал-пост в каталог."""
    if not looks_like_model_post(message):
        return None

    caption = message.caption or message.text or ""
    cleaned = clean_source_text(caption)
    if not cleaned:
        return None

    title = extract_title(cleaned, fallback=message.chat.title or "Новая модель")
    description = extract_description(cleaned, title)
    price = extract_price(caption)
    category_name = choose_category(title, description, message.chat.title or "")
    category_id = ensure_category(category_name)
    photo_file_id = message.photo[-1].file_id if message.photo else ""
    source_chat_id = message.chat.id
    source_message_id = message.message_id
    source_url = build_source_url(message)

    existing = get_catalog_import(source_chat_id, source_message_id)
    if existing:
        product_id = existing["product_id"]
        update_product(
            product_id,
            title=title,
            desc=description,
            price=price,
            photo=photo_file_id,
            cat_id=category_id,
        )
        mark_catalog_import(source_chat_id, source_message_id, product_id, title, source_url)
        return product_id, False

    product_id = add_product(
        cat_id=category_id,
        title=title,
        desc=description,
        price=price,
        photo=photo_file_id,
    )
    mark_catalog_import(source_chat_id, source_message_id, product_id, title, source_url)
    return product_id, True


async def _import_and_log(message: Message) -> None:
    """Импортировать пост и записать лог."""
    try:
        result = import_catalog_post(message)
        if result:
            product_id, created = result
            state = "создан" if created else "обновлён"
            logger.info(
                "Catalog import %s: chat=%s msg=%s product_id=%s title=%s",
                state,
                message.chat.id,
                message.message_id,
                product_id,
                message.caption or message.text or message.chat.title,
            )
            _export_products()
    except Exception as e:
        logger.exception("Failed to import post from %s: %s", message.chat.id, e)


@router.channel_post()
async def source_channel_post(message: Message):
    """Импорт новых постов из каналов (channel_post)."""
    if message.chat.id not in SOURCE_CHANNELS:
        return
    await _import_and_log(message)


@router.message(F.chat.id.in_(SOURCE_CHANNELS))
async def source_group_message(message: Message):
    """Импорт новых сообщений из супергруппы (message)."""
    await _import_and_log(message)


@router.message(F.forward_origin | F.forward_from_chat)
async def forwarded_message_import(message: Message):
    """Фолбэк: админ может переслать пост в бот — бот превратит его в карточку."""
    if message.from_user is None or message.from_user.id not in ADMIN_IDS:
        return
    try:
        result = import_catalog_post(message)
        if result:
            product_id, created = result
            state = "создана" if created else "обновлена"
            await message.answer(
                f"Карточка {state}: <b>{html_escape(message.caption or message.text or message.chat.title or 'модель')}</b>\nID: {product_id}",
                parse_mode="HTML",
            )
        else:
            await message.answer("Не удалось создать карточку из этого поста.")
    except Exception as e:
        logger.exception("Forwarded post import failed: %s", e)
        await message.answer(f"Ошибка импорта: {html_escape(str(e))}")
