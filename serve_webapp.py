"""
HTTP-сервер для Telegram Mini App @Jarvisvetogorbot
Отдаёт HTML магазина и API с товарами из SQLite

Запуск: python serve_webapp.py
Порт: 8765
"""
import json
import os
import sys
import mimetypes
import time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, quote

from config import BOT_TOKEN

# Путь к папке бота (текущая директория)
BOT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BOT_DIR, "bot_data.db")
WEBAPP_DIR = os.path.join(BOT_DIR, "webapp")
WEBAPP_FILE = os.path.join(WEBAPP_DIR, "mini_app.html")

PORT = 8765
PHOTOS_DIR = os.path.join(BOT_DIR, "product_photos")
os.makedirs(PHOTOS_DIR, exist_ok=True)
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
        print(f"[serve] photo url error: {e}")

    return ""


def get_products_from_db():
    """Получить товары из БД + демо-данные для теста"""
    products = []
    try:
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            SELECT p.id, p.title, p.description, p.price, p.photo_file_id, p.local_photo,
                   c.name as category_name, c.emoji as cat_emoji, p.stock
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE p.is_active = 1
            ORDER BY c.sort_order, p.id
        """)
        rows = c.fetchall()
        conn.close()

        for r in rows:
            photo_url = ""
            local_path = r[5] if len(r) > 5 else ""
            if local_path:
                full_photo_path = local_path if os.path.isabs(local_path) else os.path.join(PHOTOS_DIR, local_path)
                if os.path.isfile(full_photo_path):
                    photo_url = f"/api/product-photo/{r[0]}"
            elif r[4]:
                photo_url = get_telegram_file_url(r[4])

            stock = r[8] if len(r) > 8 else -1
            products.append({
                "id": r[0],
                "title": r[1],
                "desc": r[2] or "Качественная 3D-печать на заказ",
                "price": r[3] or 1000,
                "photo": r[4] or "",
                "photo_url": photo_url,
                "category": r[6] or "Прочее",
                "rating": 4.5,
                "stock": stock,
            })
    except Exception as e:
        print(f"[serve] DB error: {e}")

    # Демо-товары только если база пуста
    if not products:
        products = _demo_products()
    return products


def _demo_products():
    """Демо-товары для тестирования"""
    return [
        {"id": 101, "title": "Дракон трёхглавый", "category": "Фигурки", "price": 5490,
         "desc": "Большая коллекционная фигурка с выразительной пластикой и сложной геометрией.", "rating": 4.9},
        {"id": 102, "title": "Танк T-34-85", "category": "Игровая техника", "price": 4290,
         "desc": "Военная модель с детализированной ходовой частью и башней.", "rating": 4.8},
        {"id": 103, "title": "Шлем космодесанта", "category": "Косплей", "price": 6490,
         "desc": "Крупный косплей-элемент с посадкой под реальный размер головы.", "rating": 4.9},
        {"id": 104, "title": "Плазменная винтовка", "category": "Оружие", "price": 3890,
         "desc": "Фантастический пропс с глянцевыми плоскостями и LED-подсветкой.", "rating": 4.7},
        {"id": 105, "title": "Набор шестерён", "category": "Детали и запчасти", "price": 1690,
         "desc": "Механические детали для сборки, макетов и функциональных прототипов.", "rating": 4.6},
        {"id": 106, "title": "Лампа-куб", "category": "Интерьер", "price": 2190,
         "desc": "Минималистичный светильник с мягким рассеянным светом.", "rating": 4.6},
        {"id": 107, "title": "Рыцарь-тамплиер", "category": "Фигурки", "price": 4990,
         "desc": "Фигурка с мощным силуэтом, хорошо смотрится в витрине и под покраску.", "rating": 4.8},
        {"id": 108, "title": "Бронетранспортёр БТР-80", "category": "Игровая техника", "price": 4590,
         "desc": "Реалистичная техника с хорошей читаемостью формы.", "rating": 4.7},
        {"id": 109, "title": "Бюст героя", "category": "Фигурки", "price": 2790,
         "desc": "Классический бюст для подарка, полки или покраски в стиле game art.", "rating": 4.7},
    ]


class MiniAppHandler(BaseHTTPRequestHandler):
    """Обработчик для Mini App"""

    def log_message(self, format, *args):
        if len(args) == 3:
            print(f"[serve] {args[0]} {args[1]} {args[2]}")
        elif len(args) == 2:
            print(f"[serve] HTTP {args[0]} — {args[1]}")
        else:
            print(f"[serve] {args}")

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # API: фото товара по id — сначала local, потом Telegram
        if path.startswith('/api/product-photo/'):
            try:
                prod_id = int(path.rstrip('/').split('/')[-1])
                import sqlite3
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("SELECT photo_file_id, local_photo FROM products WHERE id=? AND is_active=1", (prod_id,))
                row = c.fetchone()
                conn.close()
                if row:
                    # Приоритет: локальное фото
                    local_path = row[1]
                    if local_path:
                        full_path = local_path if os.path.isabs(local_path) else os.path.join(PHOTOS_DIR, local_path)
                        if os.path.isfile(full_path):
                            self.send_file(full_path)
                            return
                    # Fallback: Telegram file_id
                    file_id = row[0]
                    if file_id:
                        url = get_telegram_file_url(file_id)
                        if url:
                            self.send_response(302)
                            self.send_header('Location', url)
                            self.send_header('Access-Control-Allow-Origin', '*')
                            self.end_headers()
                            return
                self.send_error(404, 'Фото не найдено')
            except (ValueError, IndexError):
                self.send_error(400, 'Неверный ID')
            return

        # API: список товаров
        if path == '/api/products':
            result = get_products_from_db()
            self.send_json(result)
            return

        # API: один товар
        if path.startswith('/api/products/'):
            try:
                prod_id = int(path.split('/')[-1])
                products = get_products_from_db()
                product = next((p for p in products if p['id'] == prod_id), None)
                if product:
                    self.send_json(product)
                else:
                    self.send_error(404, "Товар не найден")
            except (ValueError, IndexError):
                self.send_error(400, "Неверный ID")
            return

        # Health check
        if path == '/health':
            self.send_json({"status": "ok", "port": PORT})
            return

        # API: статистика для админ-дашборда
        if path == '/api/stats':
            import sqlite3
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM orders")
            total_orders = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM orders WHERE status='new'")
            new_orders = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM products WHERE is_active=1")
            total_products = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM orders WHERE created_at >= datetime('now', '-7 days')")
            week_orders = c.fetchone()[0]
            c.execute("SELECT COALESCE(SUM(total_price), 0) FROM orders WHERE status NOT IN ('cancelled')")
            total_revenue = c.fetchone()[0]
            c.execute("SELECT created_at, COUNT(*) FROM orders WHERE created_at >= datetime('now', '-30 days') GROUP BY date(created_at) ORDER BY created_at")
            orders_by_day = [{"date": r[0][:10], "count": r[1]} for r in c.fetchall()]
            conn.close()
            self.send_json({
                "total_orders": total_orders,
                "new_orders": new_orders,
                "total_products": total_products,
                "week_orders": week_orders,
                "total_revenue": total_revenue,
                "orders_by_day": orders_by_day,
            })
            return

        # Статика: отдаём mini_app.html
        file_to_serve = WEBAPP_FILE
        if path != '/' and path != '' and path != '/mini_app.html':
            safe_path = os.path.normpath(os.path.join(WEBAPP_DIR, path.lstrip('/')))
            # Security check: prevent path traversal
            if safe_path.startswith(WEBAPP_DIR) and os.path.isfile(safe_path):
                file_to_serve = safe_path

        if os.path.isfile(file_to_serve):
            self.send_file(file_to_serve)
        else:
            # Fallback to mini_app.html for SPA-like routing
            if os.path.isfile(WEBAPP_FILE):
                self.send_file(WEBAPP_FILE)
            else:
                self.send_error(404, "Файл не найден")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'X-Init-Data, Content-Type')
        self.end_headers()

    # Удаление товаров — только через Telegram bot (handlers/admin.py),
    # где проверяется is_admin(). HTTP DELETE endpoint удалён из соображений безопасности.

    def send_json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, filepath):
        mime_type, _ = mimetypes.guess_type(filepath)
        if mime_type is None:
            mime_type = 'application/octet-stream'

        try:
            with open(filepath, 'rb') as f:
                data = f.read()

            self.send_response(200)
            self.send_header('Content-Type', mime_type)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(data)
        except IOError:
            self.send_error(404, "Файл не найден")


def main():
    # Проверяем наличие HTML
    os.makedirs(WEBAPP_DIR, exist_ok=True)
    if not os.path.isfile(WEBAPP_FILE):
        print(f"HTML файл не найден: {WEBAPP_FILE}")
    else:
        size = os.path.getsize(WEBAPP_FILE)
        print(f"   HTML: {size} байт")

    server = ThreadingHTTPServer(('0.0.0.0', PORT), MiniAppHandler)
    print(f"Mini App Server запущен на http://localhost:{PORT}")
    print(f"   Магазин: http://localhost:{PORT}")
    print(f"   API: http://localhost:{PORT}/api/products")
    print(f"   База: {DB_PATH}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nСервер остановлен")
        server.server_close()


if __name__ == '__main__':
    main()
