@echo off
chcp 65001 >nul
echo =============================================
echo  Деплой магазина на GitHub Pages
echo =============================================
echo.
echo Шаг 1: Создание products.json из SQLite
cd /d "%~dp0"
python -c "
import sqlite3, json, os
db = os.path.join(os.path.dirname(__file__), 'bot_data.db')
products = []
try:
    conn = sqlite3.connect(db)
    c = conn.cursor()
    c.execute('SELECT p.id, p.title, p.description, p.price, c.name FROM products p LEFT JOIN categories c ON p.category_id = c.id WHERE p.is_active = 1')
    for r in c.fetchall():
        products.append({'id': r[0], 'title': r[1], 'desc': r[2] or '', 'price': r[3] or 1000, 'category': r[4] or 'Прочее', 'rating': 4.5})
    conn.close()
except Exception as e:
    print(f'Ошибка: {e}')
with open('webapp/products.json', 'w', encoding='utf-8') as f:
    json.dump(products, f, ensure_ascii=False, indent=2)
print(f'Сохранено {len(products)} товаров')
"
echo.
echo Шаг 2: Git init и push
echo   git init webapp/
echo   cd webapp/ ^&^& git add . ^&^& git commit -m "store"
echo   gh repo create jarvis-bot-store --public --push --source=.
echo.
echo Шаг 3: Включить GitHub Pages в настройках репозитория
echo.
echo Шаг 4: Обновить WEBAPP_URL в handlers/webapp.py
echo.
echo Или используй npx surge (без GitHub):
echo   cd webapp ^&^& npx surge --domain jarvis-store.surge.sh
