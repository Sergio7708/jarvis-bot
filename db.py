"""
База данных бота — SQLite
Все таблицы и функции для работы бота
"""
import sqlite3
import os
import json
from datetime import datetime
from config import DB_PATH


def init_db():
    """Создать таблицы при первом запуске"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Категории каталога
    c.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            emoji TEXT DEFAULT '',
            description TEXT DEFAULT '',
            sort_order INTEGER DEFAULT 0
        )
    """)

    # Товары/модели
    c.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            price INTEGER DEFAULT 0,
            photo_file_id TEXT DEFAULT '',
            local_photo TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (category_id) REFERENCES categories(id)
        )
    """)
    # Миграция: добавить local_photo если колонки нет
    try:
        c.execute("ALTER TABLE products ADD COLUMN local_photo TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    # Миграция: добавить stock если колонки нет
    try:
        c.execute("ALTER TABLE products ADD COLUMN stock INTEGER DEFAULT -1")
    except sqlite3.OperationalError:
        pass

    # Заказы
    c.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT DEFAULT '',
            product_title TEXT DEFAULT '',
            material TEXT DEFAULT '',
            color TEXT DEFAULT '',
            quantity INTEGER DEFAULT 1,
            contact TEXT DEFAULT '',
            comment TEXT DEFAULT '',
            status TEXT DEFAULT 'new',
            total_price INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # Позиции заказа (связь заказ → товары)
    c.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER,
            product_title TEXT NOT NULL,
            material TEXT DEFAULT '',
            color TEXT DEFAULT '',
            quantity INTEGER DEFAULT 1,
            price INTEGER DEFAULT 0,
            FOREIGN KEY (order_id) REFERENCES orders(id)
        )
    """)

    # Репостед — логи репостов
    c.execute("""
        CREATE TABLE IF NOT EXISTS reposted (
            message_id INTEGER PRIMARY KEY,
            source_chat_id INTEGER NOT NULL,
            reposted_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # Корзина (временные данные до оформления заказа)
    c.execute("""
        CREATE TABLE IF NOT EXISTS cart_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            product_title TEXT NOT NULL,
            price INTEGER DEFAULT 0,
            material TEXT DEFAULT '',
            color TEXT DEFAULT '',
            quantity INTEGER DEFAULT 1,
            added_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    """)

    # Импортированные карточки из Telegram-каналов
    c.execute("""
        CREATE TABLE IF NOT EXISTS catalog_imports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_chat_id INTEGER NOT NULL,
            source_message_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            source_title TEXT DEFAULT '',
            source_url TEXT DEFAULT '',
            imported_at TEXT DEFAULT (datetime('now')),
            UNIQUE(source_chat_id, source_message_id)
        )
    """)

    # Избранное
    c.execute("""
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(user_id, product_id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    """)

    # Отзывы
    c.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT DEFAULT '',
            product_id INTEGER NOT NULL,
            rating INTEGER DEFAULT 5 CHECK(rating >= 1 AND rating <= 5),
            text TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    """)

    # Подписчики на рассылку
    c.execute("""
        CREATE TABLE IF NOT EXISTS subscribers (
            user_id INTEGER PRIMARY KEY,
            username TEXT DEFAULT '',
            subscribed_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # Забаненные пользователи
    c.execute("""
        CREATE TABLE IF NOT EXISTS banned_users (
            user_id INTEGER PRIMARY KEY,
            username TEXT DEFAULT '',
            reason TEXT DEFAULT '',
            banned_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # Платежи
    c.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            user_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            payment_id TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            confirmation_url TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now')),
            paid_at TEXT
        )
    """)

    # Фотоотчёты по заказам
    c.execute("""
        CREATE TABLE IF NOT EXISTS order_photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            admin_id INTEGER NOT NULL,
            photo_file_id TEXT NOT NULL,
            caption TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (order_id) REFERENCES orders(id)
        )
    """)

    conn.commit()
    conn.close()


# ============================================================
# КАТЕГОРИИ
# ============================================================

def get_categories():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, name, emoji, description FROM categories ORDER BY sort_order, id")
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "name": r[1], "emoji": r[2], "desc": r[3]} for r in rows]


def add_category(name, emoji="", desc=""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO categories (name, emoji, description) VALUES (?, ?, ?)",
              (name, emoji, desc))
    conn.commit()
    conn.close()


def update_category(cat_id, name=None, emoji=None, desc=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if name is not None:
        c.execute("UPDATE categories SET name=? WHERE id=?", (name, cat_id))
    if emoji is not None:
        c.execute("UPDATE categories SET emoji=? WHERE id=?", (emoji, cat_id))
    if desc is not None:
        c.execute("UPDATE categories SET description=? WHERE id=?", (desc, cat_id))
    conn.commit()
    conn.close()


def delete_category(cat_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM products WHERE category_id=?", (cat_id,))
    c.execute("DELETE FROM categories WHERE id=?", (cat_id,))
    conn.commit()
    conn.close()


# ============================================================
# ТОВАРЫ
# ============================================================

def get_products(category_id=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if category_id:
        c.execute("SELECT id, title, description, price, photo_file_id, category_id, stock FROM products WHERE category_id=? AND is_active=1 ORDER BY id", (category_id,))
    else:
        c.execute("SELECT id, title, description, price, photo_file_id, category_id, stock FROM products WHERE is_active=1 ORDER BY id")
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "title": r[1], "desc": r[2], "price": r[3], "photo": r[4], "cat_id": r[5], "stock": r[6]} for r in rows]


def get_product(product_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, title, description, price, photo_file_id, local_photo, category_id, stock FROM products WHERE id=?", (product_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return {"id": row[0], "title": row[1], "desc": row[2], "price": row[3], "photo": row[4], "local_photo": row[5], "cat_id": row[6], "stock": row[7]}
    return None


def add_product(cat_id, title, desc="", price=0, photo="", stock=-1):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO products (category_id, title, description, price, photo_file_id, stock) VALUES (?, ?, ?, ?, ?, ?)",
              (cat_id, title, desc, price, photo, stock))
    conn.commit()
    conn.close()
    return c.lastrowid


def update_product(product_id, title=None, desc=None, price=None, photo=None, cat_id=None, local_photo=None, stock=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if title is not None:
        c.execute("UPDATE products SET title=? WHERE id=?", (title, product_id))
    if desc is not None:
        c.execute("UPDATE products SET description=? WHERE id=?", (desc, product_id))
    if price is not None:
        c.execute("UPDATE products SET price=? WHERE id=?", (price, product_id))
    if photo is not None:
        c.execute("UPDATE products SET photo_file_id=? WHERE id=?", (photo, product_id))
    if local_photo is not None:
        c.execute("UPDATE products SET local_photo=? WHERE id=?", (local_photo, product_id))
    if cat_id is not None:
        c.execute("UPDATE products SET category_id=? WHERE id=?", (cat_id, product_id))
    if stock is not None:
        c.execute("UPDATE products SET stock=? WHERE id=?", (stock, product_id))
    conn.commit()
    conn.close()


def delete_product(product_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM products WHERE id=?", (product_id,))
    conn.commit()
    conn.close()


def get_orders_for_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, product_title, status, created_at FROM orders WHERE user_id=? ORDER BY created_at DESC", (user_id,))
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "product": r[1], "status": r[2], "date": r[3]} for r in rows]


def search_products(query):
    """Поиск товаров по названию или описанию"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    q = f"%{query}%"
    c.execute("""
        SELECT id, title, description, price, photo_file_id, category_id
        FROM products WHERE is_active=1 AND (title LIKE ? OR description LIKE ?)
        ORDER BY id LIMIT 20
    """, (q, q))
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "title": r[1], "desc": r[2], "price": r[3], "photo": r[4], "cat_id": r[5]} for r in rows]


def get_catalog_import(source_chat_id, source_message_id):
    """Проверить, импортирована ли уже карточка из конкретного поста."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT product_id, source_title, source_url FROM catalog_imports WHERE source_chat_id=? AND source_message_id=?",
        (source_chat_id, source_message_id),
    )
    row = c.fetchone()
    conn.close()
    if row:
        return {"product_id": row[0], "source_title": row[1], "source_url": row[2]}
    return None


def mark_catalog_import(source_chat_id, source_message_id, product_id, source_title="", source_url=""):
    """Запомнить связь между исходным постом и товаром."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        INSERT OR REPLACE INTO catalog_imports
        (source_chat_id, source_message_id, product_id, source_title, source_url)
        VALUES (?, ?, ?, ?, ?)
        """,
        (source_chat_id, source_message_id, product_id, source_title, source_url),
    )
    conn.commit()
    conn.close()


# ============================================================
# ЗАКАЗЫ
# ============================================================

def create_order(user_id, username="", product_title="", material="", color="", qty=1, contact="", comment="", total_price=0):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO orders (user_id, username, product_title, material, color, quantity, contact, comment, total_price)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, username, product_title, material, color, qty, contact, comment, total_price))
    conn.commit()
    order_id = c.lastrowid
    conn.close()
    return order_id


def get_order(order_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT id, user_id, username, product_title, material, color, quantity, contact, comment, status, created_at, total_price
        FROM orders WHERE id=?
    """, (order_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return {
            "id": row[0], "user_id": row[1], "username": row[2],
            "product": row[3], "material": row[4], "color": row[5],
            "qty": row[6], "contact": row[7], "comment": row[8],
            "status": row[9], "date": row[10], "total_price": row[11]
        }
    return None


def get_orders_count(status=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if status:
        c.execute("SELECT COUNT(*) FROM orders WHERE status=?", (status,))
    else:
        c.execute("SELECT COUNT(*) FROM orders")
    count = c.fetchone()[0]
    conn.close()
    return count


def get_orders(status=None, limit=50, offset=0):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if status:
        c.execute("""
            SELECT id, user_id, username, product_title, material, color, quantity, contact, comment, status, created_at, total_price
            FROM orders WHERE status=? ORDER BY created_at DESC LIMIT ? OFFSET ?
        """, (status, limit, offset))
    else:
        c.execute("""
            SELECT id, user_id, username, product_title, material, color, quantity, contact, comment, status, created_at, total_price
            FROM orders ORDER BY created_at DESC LIMIT ? OFFSET ?
        """, (limit, offset))
    rows = c.fetchall()
    conn.close()
    return [{
        "id": r[0], "user_id": r[1], "username": r[2],
        "product": r[3], "material": r[4], "color": r[5],
        "qty": r[6], "contact": r[7], "comment": r[8],
        "status": r[9], "date": r[10], "total_price": r[11]
    } for r in rows]


def get_user_orders(user_id, limit=20):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT id, product_title, status, total_price, created_at
        FROM orders WHERE user_id=? ORDER BY created_at DESC LIMIT ?
    """, (user_id, limit))
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "product": r[1], "status": r[2], "total_price": r[3], "date": r[4]} for r in rows]


def get_user_orders_count(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM orders WHERE user_id=?", (user_id,))
    count = c.fetchone()[0]
    conn.close()
    return count


def update_order_status(order_id, new_status):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE orders SET status=?, updated_at=datetime('now') WHERE id=?",
              (new_status, order_id))
    conn.commit()
    conn.close()


def add_order_item(order_id, product_id, product_title, material="", color="", qty=1, price=0):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO order_items (order_id, product_id, product_title, material, color, quantity, price)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (order_id, product_id, product_title, material, color, qty, price))
    conn.commit()
    conn.close()


def get_order_items(order_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, product_title, material, color, quantity, price FROM order_items WHERE order_id=?", (order_id,))
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "title": r[1], "material": r[2], "color": r[3], "qty": r[4], "price": r[5]} for r in rows]


# ============================================================
# КОРЗИНА
# ============================================================

def add_to_cart(user_id, product_id, product_title, price=0, material="", color="", qty=1):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Проверяем, есть ли уже такой товар в корзине
    c.execute("SELECT id, quantity FROM cart_items WHERE user_id=? AND product_id=? AND material=? AND color=?",
              (user_id, product_id, material, color))
    existing = c.fetchone()
    if existing:
        c.execute("UPDATE cart_items SET quantity=quantity+? WHERE id=?", (qty, existing[0]))
    else:
        c.execute("""
            INSERT INTO cart_items (user_id, product_id, product_title, price, material, color, quantity)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, product_id, product_title, price, material, color, qty))
    conn.commit()
    conn.close()


def get_cart(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT id, product_id, product_title, price, material, color, quantity
        FROM cart_items WHERE user_id=? ORDER BY added_at
    """, (user_id,))
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "product_id": r[1], "title": r[2], "price": r[3], "material": r[4], "color": r[5], "qty": r[6]} for r in rows]


def remove_from_cart(item_id, user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM cart_items WHERE id=? AND user_id=?", (item_id, user_id))
    conn.commit()
    conn.close()


def clear_cart(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM cart_items WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()


def cart_total(user_id):
    items = get_cart(user_id)
    return sum(item["price"] * item["qty"] for item in items)


# ============================================================
# ИЗБРАННОЕ
# ============================================================

def add_favorite(user_id, product_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("INSERT OR IGNORE INTO favorites (user_id, product_id) VALUES (?, ?)", (user_id, product_id))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    conn.close()


def remove_favorite(user_id, product_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM favorites WHERE user_id=? AND product_id=?", (user_id, product_id))
    conn.commit()
    conn.close()


def is_favorite(user_id, product_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM favorites WHERE user_id=? AND product_id=?", (user_id, product_id))
    row = c.fetchone()
    conn.close()
    return row is not None


def toggle_favorite(user_id, product_id):
    """Добавить/удалить товар из избранного"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM favorites WHERE user_id=? AND product_id=?", (user_id, product_id))
    row = c.fetchone()
    if row:
        c.execute("DELETE FROM favorites WHERE id=?", (row[0],))
    else:
        c.execute("INSERT INTO favorites (user_id, product_id) VALUES (?, ?)", (user_id, product_id))
    conn.commit()
    conn.close()


def get_favorites(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT p.id, p.title, p.description, p.price, p.photo_file_id, p.category_id
        FROM favorites f
        JOIN products p ON p.id = f.product_id
        WHERE f.user_id=? AND p.is_active=1
        ORDER BY f.created_at DESC
    """, (user_id,))
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "title": r[1], "desc": r[2], "price": r[3], "photo": r[4], "cat_id": r[5]} for r in rows]


# ============================================================
# ОТЗЫВЫ
# ============================================================

def add_review(user_id, username, product_id, rating, text=""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO reviews (user_id, username, product_id, rating, text)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, username, product_id, rating, text))
    conn.commit()
    conn.close()
    return c.lastrowid


def get_product_reviews(product_id, limit=10):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT id, user_id, username, rating, text, created_at
        FROM reviews WHERE product_id=? ORDER BY created_at DESC LIMIT ?
    """, (product_id, limit))
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "user_id": r[1], "username": r[2], "rating": r[3], "text": r[4], "date": r[5]} for r in rows]


def get_product_avg_rating(product_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT AVG(rating), COUNT(*) FROM reviews WHERE product_id=?", (product_id,))
    row = c.fetchone()
    conn.close()
    return {"avg": round(row[0], 1) if row[0] else 0, "count": row[1] or 0}


# ============================================================
# ПОДПИСЧИКИ
# ============================================================

def subscribe_user(user_id, username=""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO subscribers (user_id, username) VALUES (?, ?)", (user_id, username))
    conn.commit()
    conn.close()


def unsubscribe_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM subscribers WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()


def is_subscribed(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM subscribers WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row is not None


def get_subscribers():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id, username, subscribed_at FROM subscribers ORDER BY subscribed_at")
    rows = c.fetchall()
    conn.close()
    return [{"user_id": r[0], "username": r[1], "date": r[2]} for r in rows]


# ============================================================
# БАН-ЛИСТ
# ============================================================

def ban_user(user_id, username="", reason=""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO banned_users (user_id, username, reason) VALUES (?, ?, ?)",
              (user_id, username, reason))
    conn.commit()
    conn.close()


def unban_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM banned_users WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()


def is_banned(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM banned_users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row is not None


def get_banned_users():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id, username, reason, banned_at FROM banned_users ORDER BY banned_at DESC")
    rows = c.fetchall()
    conn.close()
    return [{"user_id": r[0], "username": r[1], "reason": r[2], "date": r[3]} for r in rows]


# ============================================================
# ПЛАТЕЖИ (ЮKassa)
# ============================================================

def create_payment(order_id, user_id, amount, confirmation_url=""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO payments (order_id, user_id, amount, confirmation_url)
        VALUES (?, ?, ?, ?)
    """, (order_id, user_id, amount, confirmation_url))
    conn.commit()
    payment_db_id = c.lastrowid
    conn.close()
    return payment_db_id


def update_payment_status(payment_db_id, payment_id, status):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if status == "succeeded":
        c.execute("""
            UPDATE payments SET status=?, payment_id=?, paid_at=datetime('now')
            WHERE id=?
        """, (status, payment_id, payment_db_id))
    else:
        c.execute("""
            UPDATE payments SET status=?, payment_id=?
            WHERE id=?
        """, (status, payment_id, payment_db_id))
    conn.commit()
    conn.close()


def get_payment(order_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, order_id, amount, status, confirmation_url, payment_id, created_at FROM payments WHERE order_id=? ORDER BY id DESC LIMIT 1", (order_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return {"id": row[0], "order_id": row[1], "amount": row[2], "status": row[3], "url": row[4], "payment_id": row[5], "date": row[6]}
    return None


# ============================================================
# ФОТООТЧЁТЫ
# ============================================================

def add_order_photo(order_id, admin_id, photo_file_id, caption=""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO order_photos (order_id, admin_id, photo_file_id, caption)
        VALUES (?, ?, ?, ?)
    """, (order_id, admin_id, photo_file_id, caption))
    conn.commit()
    conn.close()


def get_order_photos(order_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, photo_file_id, caption, created_at FROM order_photos WHERE order_id=? ORDER BY created_at", (order_id,))
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "photo": r[1], "caption": r[2], "date": r[3]} for r in rows]


# ============================================================
# СТАТИСТИКА
# ============================================================

def get_stats():
    """Расширенная статистика"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    cats = c.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
    prods = c.execute("SELECT COUNT(*) FROM products WHERE is_active=1").fetchone()[0]
    total_orders = c.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    new_orders = c.execute("SELECT COUNT(*) FROM orders WHERE status='new'").fetchone()[0]
    active = c.execute("SELECT COUNT(*) FROM orders WHERE status IN ('accepted','working','printing')").fetchone()[0]
    done = c.execute("SELECT COUNT(*) FROM orders WHERE status='shipped'").fetchone()[0]
    cancelled = c.execute("SELECT COUNT(*) FROM orders WHERE status='cancelled'").fetchone()[0]

    # Выручка
    revenue_row = c.execute("SELECT COALESCE(SUM(total_price),0) FROM orders WHERE status='shipped'").fetchone()
    revenue = revenue_row[0] if revenue_row else 0

    # Популярные товары
    c.execute("""
        SELECT product_title, COUNT(*) as cnt FROM orders
        WHERE product_title != '' GROUP BY product_title ORDER BY cnt DESC LIMIT 5
    """)
    top_products = c.fetchall()

    # Подписчики
    subs = c.execute("SELECT COUNT(*) FROM subscribers").fetchone()[0]

    conn.close()
    return {
        "categories": cats,
        "products": prods,
        "orders_total": total_orders,
        "orders_new": new_orders,
        "orders_active": active,
        "orders_done": done,
        "orders_cancelled": cancelled,
        "revenue": revenue,
        "top_products": top_products,
        "subscribers": subs,
    }


# ============================================================
# БЭКАП
# ============================================================

def backup_db(backup_dir=None):
    """Создать копию файла БД"""
    import shutil
    from datetime import datetime

    if backup_dir is None:
        backup_dir = os.path.join(os.path.dirname(DB_PATH), "backups")

    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(backup_dir, f"bot_data_{timestamp}.db")

    shutil.copy2(DB_PATH, backup_path)
    return backup_path


# ============================================================
# РЕПОСТЕД (логирование)
# ============================================================

def is_reposted(msg_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM reposted WHERE message_id=?", (msg_id,))
    row = c.fetchone()
    conn.close()
    return row is not None


def mark_reposted(msg_id, source_chat_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO reposted (message_id, source_chat_id) VALUES (?, ?)",
              (msg_id, source_chat_id))
    conn.commit()
    conn.close()


def get_last_reposted(source_chat_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT MAX(message_id) FROM reposted WHERE source_chat_id=?",
              (source_chat_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row[0] else 0
