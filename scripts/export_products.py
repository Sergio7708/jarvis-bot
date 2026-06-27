"""
Скрипт экспорта products.json для статического хостинга (GitHub Pages).
Собирает все товары из БД, конвертирует photo_file_id в URL и сохраняет как JSON.

Запуск: python scripts/export_products.py
Вывод: webapp/products.json

Для корректной работы нужен BOT_TOKEN в config.py.
"""
import json
import os
import sys
import time
from urllib.parse import quote

# Добавляем корень проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import BOT_TOKEN

BOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BOT_DIR, "bot_data.db")
OUTPUT_PATH = os.path.join(BOT_DIR, "webapp", "products.json")
PHOTOS_DIR = os.path.join(BOT_DIR, "product_photos")

_PHOTO_URL_CACHE = {}


def get_telegram_file_url(file_id):
    """Преобразовать Telegram file_id в прямую ссылку на файл."""
    if not file_id:
        return ""
    now = time.time()
    cached = _PHOTO_URL_CACHE.get(file_id)
    if cached and cached[0] > now:
        return cached[1]
    try:
        import urllib.request
        api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={quote(str(file_id))}"
        req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        if payload.get("ok") and payload.get("result", {}).get("file_path"):
            file_path = payload["result"]["file_path"]
            url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
            _PHOTO_URL_CACHE[file_id] = (now + 3600, url)
            return url
    except Exception as e:
        print(f"[export] photo url error: {e}")
    return ""


def main():
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT p.id, p.title, p.description, p.price, p.photo_file_id, p.local_photo,
               c.name as category_name, p.stock
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.is_active = 1
        ORDER BY c.sort_order, p.id
    """)
    rows = c.fetchall()
    conn.close()

    products = []
    for r in rows:
        pid, title, desc, price, file_id, local_photo, category, stock = r

        # Определяем URL фото:
        # Приоритет 1: прямая ссылка Telegram (работает везде, включая GitHub Pages)
        # Приоритет 2: локальный путь (для localhost)
        photo_url = ""
        photo_rel = ""
        if file_id:
            photo_url = get_telegram_file_url(file_id)
        if not photo_url and local_photo:
            photo_url = f"/product_photos/{pid}.jpg"
            photo_rel = f"product_photos/{pid}.jpg"

        products.append({
            "id": pid,
            "title": title,
            "desc": desc or "Качественная 3D-печать на заказ",
            "price": price or 1000,
            "photo_url": photo_url,
            "category": category or "Прочее",
            "rating": 4.5,
            "stock": stock or -1,
        })

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)

    print(f"[export] Экспортировано {len(products)} товаров в {OUTPUT_PATH}")

    # Копируем product_photos в webapp/
    dest_photos = os.path.join(os.path.dirname(OUTPUT_PATH), "product_photos")
    os.makedirs(dest_photos, exist_ok=True)
    copied = 0
    for pid in range(1, max(r[0] for r in rows) + 1):
        src = os.path.join(PHOTOS_DIR, f"{pid}.jpg")
        dst = os.path.join(dest_photos, f"{pid}.jpg")
        if os.path.isfile(src) and not os.path.isfile(dst):
            import shutil
            shutil.copy2(src, dst)
            copied += 1
    print(f"[export] Скопировано {copied} новых фото в webapp/product_photos")


if __name__ == "__main__":
    main()
